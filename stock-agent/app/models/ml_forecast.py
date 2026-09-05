"""API/domain response models for the ML multi-horizon forecasting
subsystem (`app.forecasting.ml`). Kept separate from
`app.models.forecasting` (the existing deterministic `ForecastResult`)
since this is a parallel system, not a replacement -- see spec section
27, "keep existing technical forecast as baseline."
"""

from pydantic import BaseModel, Field


class QuantileEstimate(BaseModel):
    p10: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p90: float | None = None


class ModelAgreementEntry(BaseModel):
    model_name: str
    point_return: float
    weight: float


class AnalogSummary(BaseModel):
    sample_size: int
    is_reliable: bool
    positive_rate: float | None = None
    negative_rate: float | None = None
    mean_return: float | None = None
    median_return: float | None = None
    quantiles: QuantileEstimate | None = None


class HistoricalAccuracy(BaseModel):
    sample_size: int
    mae: float | None = None
    rmse: float | None = None
    directional_accuracy: float | None = None
    brier_score: float | None = None
    interval_coverage_80: float | None = None


class ForecastDriversResponse(BaseModel):
    positive_drivers: list[str] = Field(default_factory=list)
    negative_drivers: list[str] = Field(default_factory=list)


class MlHorizonForecast(BaseModel):
    horizon: str
    target_date: str
    current_price: float
    expected_return: float
    expected_price: float
    quantiles: QuantileEstimate
    probability_positive: float
    forecast_quality: str
    quality_score: float
    quality_reasons: list[str]
    model_agreement: float
    model_outputs: list[ModelAgreementEntry]
    drivers: ForecastDriversResponse
    analog: AnalogSummary
    historical_accuracy: HistoricalAccuracy | None = None
    change_from_previous: dict | None = None


class NewsImpactEventSummary(BaseModel):
    event_type: str
    sample_size: int
    is_reliable: bool
    median_return_5d: float | None = None
    median_return_14d: float | None = None
    positive_rate_5d: float | None = None
    positive_rate_14d: float | None = None


class RecentNewsItem(BaseModel):
    headline: str
    published_at: str
    event_type: str
    sentiment: str
    market_timing: str
    url: str | None = None


class NewsImpactSection(BaseModel):
    recent_events: list[RecentNewsItem] = Field(default_factory=list)
    historical_statistics: list[NewsImpactEventSummary] = Field(default_factory=list)
    data_available: bool = False
    note: str | None = None


class DataQuality(BaseModel):
    price_history_days: int
    fundamentals_available: bool
    news_available: bool
    regime: str
    training_data_end_date: str | None = None


class MlForecastResult(BaseModel):
    ticker: str
    generated_at: str
    data_date: str | None = None
    current_price: float
    regime: str
    horizons: dict[str, MlHorizonForecast]
    news_impact: NewsImpactSection
    data_quality: DataQuality
    model_version: str
    feature_version: str
    news_model_version: str
    warnings: list[str] = Field(default_factory=list)
