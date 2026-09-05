"""Prediction-time orchestrator (spec section 2's full pipeline diagram,
minus training -- see `app.forecasting.ml.training` for that half).
Loads pre-trained artifacts and produces a fast per-ticker forecast; it
never fits a model itself (spec section 32: "Prediction should be
fast. Training should happen through a dedicated service/job/command").

Degrades per spec section 28 at every stage: no trained artifacts -> a
naive-only, LOW-quality result with an explicit warning; too little
price history for a ticker -> the same; no news client/persistence
wired in -> `news_impact.data_available=False` rather than an error.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.forecasting.ml.analog import find_analogs
from app.forecasting.ml.artifacts import ArtifactStore
from app.forecasting.ml.data import MlPriceHistoryService
from app.forecasting.ml.ensemble import ModelOutput, combine
from app.forecasting.ml.explain import explain_forecast
from app.forecasting.ml.features import (
    FEATURE_COLUMNS,
    RELATIVE_STRENGTH_COLUMNS,
    build_price_features,
    build_relative_strength_features,
)
from app.forecasting.ml.horizons import ALL_HORIZONS, HORIZON_TRADING_DAYS, MlHorizon
from app.forecasting.ml.models.analog_model import HistoricalAnalogModel
from app.forecasting.ml.news.event_study import (
    MIN_EVENT_STUDY_SAMPLE_SIZE,
    aggregate_event_statistics,
    compute_reaction,
)
from app.forecasting.ml.news.ingestion import NewsEventIngestionService
from app.forecasting.ml.news.models import EventType
from app.forecasting.ml.persistence import MlForecastPersistence, news_event_row_to_domain
from app.forecasting.ml.quality import QualityInputs, assess_quality
from app.forecasting.ml.regime import Regime, classify_regime
from app.forecasting.ml.versions import FEATURE_VERSION, MODEL_VERSION, NEWS_MODEL_VERSION
from app.models.ml_forecast import (
    AnalogSummary,
    DataQuality,
    ForecastDriversResponse,
    HistoricalAccuracy,
    MlForecastResult,
    MlHorizonForecast,
    ModelAgreementEntry,
    NewsImpactEventSummary,
    NewsImpactSection,
    QuantileEstimate,
    RecentNewsItem,
)

logger = logging.getLogger(__name__)

ALL_FEATURE_COLUMNS = FEATURE_COLUMNS + RELATIVE_STRENGTH_COLUMNS
_MODEL_NAMES = ("naive_zero_return", "historical_mean_return", "random_forest", "gradient_boosting_quantile")


@dataclass
class _LoadedArtifacts:
    weights: dict[str, dict[str, float]]
    pooled_dataset: pd.DataFrame
    training_data_end_date: str
    models_by_horizon: dict[MlHorizon, dict[str, object]]


class MlForecastPipeline:
    def __init__(
        self,
        *,
        artifact_store: ArtifactStore | None = None,
        price_service: MlPriceHistoryService | None = None,
        news_ingestion: NewsEventIngestionService | None = None,
        persistence: MlForecastPersistence | None = None,
    ) -> None:
        self._artifact_store = artifact_store or ArtifactStore()
        self._price_service = price_service or MlPriceHistoryService()
        self._news_ingestion = news_ingestion
        self._persistence = persistence

    def _load_artifacts(self) -> _LoadedArtifacts | None:
        if not self._artifact_store.is_trained:
            return None
        pooled = self._artifact_store.load_pooled_dataset()
        weights = self._artifact_store.load_weights()
        manifest = self._artifact_store.load_manifest()
        if pooled is None or weights is None or manifest is None:
            return None
        models_by_horizon: dict[MlHorizon, dict[str, object]] = {}
        for horizon in ALL_HORIZONS:
            models: dict[str, object] = {}
            for name in _MODEL_NAMES:
                model = self._artifact_store.load_model(horizon, name)
                if model is not None:
                    models[name] = model
            if models:
                models_by_horizon[horizon] = models
        return _LoadedArtifacts(
            weights=weights, pooled_dataset=pooled,
            training_data_end_date=manifest.training_data_end_date, models_by_horizon=models_by_horizon,
        )

    async def predict(self, ticker: str, *, company_name: str | None = None) -> MlForecastResult:
        ticker = ticker.strip().upper()
        warnings: list[str] = []
        generated_at = datetime.now(timezone.utc)

        price_result = await self._price_service.get_history(ticker, period="5y")
        if not price_result.is_usable:
            warnings.append(f"No price history available for {ticker}: {price_result.warning}")
            return _empty_result(ticker, generated_at, warnings)

        benchmark_result = await self._price_service.get_benchmark_history(period="5y")
        benchmark_close = benchmark_result.frame["close"] if benchmark_result.is_usable else None

        price_features = build_price_features(price_result.frame)
        if benchmark_close is not None:
            relative = build_relative_strength_features(price_result.frame["close"], benchmark_close)
            price_features = price_features.join(relative)

        current_price = float(price_result.frame["close"].iloc[-1])
        current_row = price_features.iloc[-1]
        regime = classify_regime(current_row)
        feature_columns_present = [c for c in ALL_FEATURE_COLUMNS if c in price_features.columns]
        feature_completeness = float(current_row[feature_columns_present].notna().mean()) if feature_columns_present else 0.0

        artifacts = self._load_artifacts()
        if artifacts is None:
            warnings.append("ML models are not yet trained -- run `python -m app.forecasting.ml.backtest --train`. Serving a naive baseline only.")

        news_impact, recent_events = await self._build_news_impact(ticker, company_name)

        current_features_row = current_row.reindex(feature_columns_present)
        current_features_frame = current_features_row.to_frame().T

        data_date = price_result.frame.index[-1]
        horizons: dict[str, MlHorizonForecast] = {}
        for horizon in ALL_HORIZONS:
            target_date = (data_date + pd.tseries.offsets.BDay(HORIZON_TRADING_DAYS[horizon])).date().isoformat()
            horizons[horizon.value] = await self._predict_horizon(
                horizon=horizon, ticker=ticker, current_price=current_price,
                current_row=current_row, current_features_frame=current_features_frame,
                feature_columns=feature_columns_present, regime=regime,
                feature_completeness=feature_completeness, artifacts=artifacts, target_date=target_date,
            )

        if self._persistence is not None and artifacts is not None:
            await self._persist_predictions(ticker, price_result.frame.index[-1], current_price, horizons, regime.value)

        return MlForecastResult(
            ticker=ticker,
            generated_at=generated_at.isoformat(),
            data_date=data_date.date().isoformat(),
            current_price=current_price,
            regime=regime.value,
            horizons=horizons,
            news_impact=news_impact,
            data_quality=DataQuality(
                price_history_days=len(price_result.frame),
                fundamentals_available=False,
                news_available=news_impact.data_available,
                regime=regime.value,
                training_data_end_date=artifacts.training_data_end_date if artifacts else None,
            ),
            model_version=MODEL_VERSION,
            feature_version=FEATURE_VERSION,
            news_model_version=NEWS_MODEL_VERSION,
            warnings=warnings,
        )

    async def _predict_horizon(
        self, *, horizon: MlHorizon, ticker: str, current_price: float, current_row: pd.Series,
        current_features_frame: pd.DataFrame, feature_columns: list[str], regime: Regime,
        feature_completeness: float, artifacts: _LoadedArtifacts | None, target_date: str,
    ) -> MlHorizonForecast:
        model_outputs: list[ModelOutput] = []
        weights = artifacts.weights.get(horizon.value, {}) if artifacts else {}

        if artifacts is not None and horizon in artifacts.models_by_horizon:
            for name, model in artifacts.models_by_horizon[horizon].items():
                try:
                    point = float(model.predict(current_features_frame)[0])
                    distribution_raw = model.predict_distribution(current_features_frame)
                    distribution = (
                        {k: float(v[0]) for k, v in distribution_raw.items()} if distribution_raw is not None else None
                    )
                    prob_raw = model.predict_probability_positive(current_features_frame)
                    prob = float(prob_raw[0]) if prob_raw is not None and not np.isnan(prob_raw[0]) else None
                except Exception as exc:  # noqa: BLE001 - a single bad model must not sink the whole forecast
                    logger.warning("ml_model_predict_failed ticker=%s horizon=%s model=%s error=%s", ticker, horizon, name, exc)
                    continue
                model_outputs.append(ModelOutput(name, point, distribution, prob, weights.get(name, 0.0)))
        else:
            model_outputs.append(ModelOutput("naive_zero_return", 0.0, None, 0.5, 1.0))

        analog_stats = None
        if artifacts is not None:
            target_col = f"target_return_{horizon.value}"
            if target_col in artifacts.pooled_dataset.columns:
                pool = artifacts.pooled_dataset.dropna(subset=feature_columns + [target_col])
                analog_result = find_analogs(query_features=current_row, candidate_pool=pool)
                analog_stats = analog_result.horizon_stats[horizon]
                if analog_stats.is_reliable:
                    model_outputs.append(
                        ModelOutput(
                            HistoricalAnalogModel.name, analog_stats.mean_return, analog_stats.quantiles,
                            analog_stats.positive_rate, weights.get("historical_analog", 0.15 if len(model_outputs) else 1.0),
                        )
                    )

        ensemble = combine(model_outputs)
        expected_price = current_price * (1 + ensemble.expected_return)
        quantiles = QuantileEstimate(**{k: current_price * (1 + v) for k, v in ensemble.quantiles.items()})

        historical_accuracy = None
        if self._persistence is not None:
            perf_row = await self._persistence.get_performance(horizon=horizon.value)
            if perf_row is not None:
                historical_accuracy = HistoricalAccuracy(
                    sample_size=perf_row.sample_size,
                    mae=float(perf_row.mae) if perf_row.mae is not None else None,
                    rmse=float(perf_row.rmse) if perf_row.rmse is not None else None,
                    directional_accuracy=float(perf_row.directional_accuracy) if perf_row.directional_accuracy is not None else None,
                    brier_score=float(perf_row.brier_score) if perf_row.brier_score is not None else None,
                    interval_coverage_80=float(perf_row.interval_coverage_80) if perf_row.interval_coverage_80 is not None else None,
                )

        interval_width = None
        if ensemble.quantiles.get("p90") is not None and ensemble.quantiles.get("p10") is not None:
            interval_width = ensemble.quantiles["p90"] - ensemble.quantiles["p10"]

        quality = assess_quality(
            QualityInputs(
                analog_sample_size=analog_stats.sample_size if analog_stats else 0,
                model_agreement=ensemble.model_agreement,
                directional_accuracy=historical_accuracy.directional_accuracy if historical_accuracy else None,
                interval_width=interval_width,
                annualized_volatility=float(current_row.get("volatility_20d")) if pd.notna(current_row.get("volatility_20d")) else None,
                feature_completeness=feature_completeness,
                regime_is_unknown=regime == Regime.UNKNOWN,
            )
        )
        drivers = explain_forecast(features=current_row, regime=regime, analog_stats=analog_stats)

        return MlHorizonForecast(
            horizon=horizon.value,
            target_date=target_date,
            current_price=current_price,
            expected_return=ensemble.expected_return,
            expected_price=expected_price,
            quantiles=quantiles,
            probability_positive=ensemble.probability_positive,
            forecast_quality=quality.quality.value,
            quality_score=quality.score,
            quality_reasons=quality.reasons,
            model_agreement=ensemble.model_agreement,
            model_outputs=[ModelAgreementEntry(model_name=m.model_name, point_return=m.point_return, weight=m.weight) for m in model_outputs],
            drivers=ForecastDriversResponse(positive_drivers=drivers.positive_drivers, negative_drivers=drivers.negative_drivers),
            analog=_analog_summary(analog_stats),
            historical_accuracy=historical_accuracy,
        )

    async def _build_news_impact(self, ticker: str, company_name: str | None) -> tuple[NewsImpactSection, list]:
        if self._news_ingestion is None:
            return NewsImpactSection(data_available=False, note="News provider not configured"), []

        try:
            prior_events = []
            if self._persistence is not None:
                prior_rows = await self._persistence.get_news_events(ticker, limit=50)
                prior_events = [news_event_row_to_domain(r) for r in prior_rows]
            fresh_events = await self._news_ingestion.fetch_and_classify(
                ticker=ticker, company_name=company_name, recent_events=prior_events
            )
            if self._persistence is not None and fresh_events:
                await self._persistence.save_news_events(fresh_events)
        except Exception as exc:  # noqa: BLE001 - news is a modifier, never allowed to break the forecast
            logger.warning("ml_news_impact_failed ticker=%s error=%s", ticker, exc)
            return NewsImpactSection(data_available=False, note="News lookup failed"), []

        all_events = fresh_events + prior_events
        recent = sorted(all_events, key=lambda e: e.published_at, reverse=True)[:10]
        recent_items = [
            RecentNewsItem(
                headline=e.headline, published_at=e.published_at.isoformat(), event_type=e.event_type.value,
                sentiment=e.sentiment.value, market_timing=e.market_timing.value, url=e.url,
            )
            for e in recent
        ]

        historical_stats: list[NewsImpactEventSummary] = []
        if self._persistence is not None:
            all_history = await self._persistence.get_all_news_events()
            price_result = await self._price_service.get_history(ticker, period="5y")
            if price_result.is_usable:
                by_type: dict[EventType, list] = {}
                for row in all_history:
                    event = news_event_row_to_domain(row)
                    if event.event_type not in {e.event_type for e in recent}:
                        continue
                    reaction = compute_reaction(event, stock_close=price_result.frame["close"], stock_volume=price_result.frame["volume"])
                    if reaction is not None:
                        by_type.setdefault(event.event_type, []).append(reaction)
                for event_type, reactions in by_type.items():
                    stats = aggregate_event_statistics(reactions, group_key=event_type.value)
                    historical_stats.append(
                        NewsImpactEventSummary(
                            event_type=event_type.value, sample_size=stats.sample_size,
                            is_reliable=stats.is_reliable,
                            median_return_5d=stats.median_return_by_horizon.get("return_5d"),
                            median_return_14d=stats.median_return_by_horizon.get("return_14d"),
                            positive_rate_5d=stats.positive_rate_by_horizon.get("return_5d"),
                            positive_rate_14d=stats.positive_rate_by_horizon.get("return_14d"),
                        )
                    )

        note = None
        if historical_stats and not any(s.is_reliable for s in historical_stats):
            note = f"Historical event samples are below the reliability threshold ({MIN_EVENT_STUDY_SAMPLE_SIZE}) -- statistics will improve as more news accumulates."
        elif not historical_stats:
            note = "No historical event-reaction data accumulated yet for this ticker's recent event types."

        return (
            NewsImpactSection(recent_events=recent_items, historical_statistics=historical_stats, data_available=bool(recent_items), note=note),
            recent,
        )

    async def _persist_predictions(self, ticker: str, data_date: pd.Timestamp, current_price: float, horizons: dict[str, MlHorizonForecast], regime_value: str) -> None:
        from app.db.models import ForecastPredictionRow

        for horizon_value, forecast in horizons.items():
            horizon = MlHorizon(horizon_value)
            target_date = (data_date + pd.tseries.offsets.BDay(HORIZON_TRADING_DAYS[horizon])).date()
            row = ForecastPredictionRow(
                ticker=ticker,
                prediction_timestamp=datetime.now(timezone.utc),
                data_timestamp=data_date.date(),
                horizon=horizon_value,
                model_version=MODEL_VERSION,
                feature_version=FEATURE_VERSION,
                news_feature_version=NEWS_MODEL_VERSION,
                current_price=current_price,
                predicted_return=forecast.expected_return,
                predicted_price=forecast.expected_price,
                p10=forecast.quantiles.p10, p25=forecast.quantiles.p25, p50=forecast.quantiles.p50,
                p75=forecast.quantiles.p75, p90=forecast.quantiles.p90,
                probability_positive=forecast.probability_positive,
                regime=regime_value,
                forecast_quality=forecast.forecast_quality,
                metadata_json="{}",
                target_date=target_date,
            )
            await self._persistence.save_prediction(row)


def _analog_summary(stats) -> AnalogSummary:
    if stats is None:
        return AnalogSummary(sample_size=0, is_reliable=False)
    return AnalogSummary(
        sample_size=stats.sample_size, is_reliable=stats.is_reliable,
        positive_rate=stats.positive_rate, negative_rate=stats.negative_rate,
        mean_return=stats.mean_return, median_return=stats.median_return,
        quantiles=QuantileEstimate(**stats.quantiles) if stats.quantiles else None,
    )


def _empty_result(ticker: str, generated_at: datetime, warnings: list[str]) -> MlForecastResult:
    empty_horizon = lambda h: MlHorizonForecast(  # noqa: E731
        horizon=h.value, target_date=generated_at.date().isoformat(), current_price=0.0, expected_return=0.0, expected_price=0.0,
        quantiles=QuantileEstimate(), probability_positive=0.5, forecast_quality="LOW",
        quality_score=0.0, quality_reasons=["No price data available"], model_agreement=0.0,
        model_outputs=[], drivers=ForecastDriversResponse(), analog=AnalogSummary(sample_size=0, is_reliable=False),
    )
    return MlForecastResult(
        ticker=ticker, generated_at=generated_at.isoformat(), current_price=0.0, regime=Regime.UNKNOWN.value,
        horizons={h.value: empty_horizon(h) for h in ALL_HORIZONS},
        news_impact=NewsImpactSection(data_available=False, note="No price data available"),
        data_quality=DataQuality(price_history_days=0, fundamentals_available=False, news_available=False, regime=Regime.UNKNOWN.value),
        model_version=MODEL_VERSION, feature_version=FEATURE_VERSION, news_model_version=NEWS_MODEL_VERSION,
        warnings=warnings,
    )
