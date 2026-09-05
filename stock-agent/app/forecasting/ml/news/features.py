"""News features for the prediction pipeline (spec section 14).

Every input list here (`events_as_of`) must already be filtered by the
caller to `published_at <= as_of` -- this module performs no time
filtering itself, mirroring the leakage-safety contract of
`app.forecasting.ml.analog.find_analogs`. `historical_event_stats` must
similarly be computed only from events strictly before `as_of` (see
`app.forecasting.ml.news.event_study.aggregate_event_statistics` on a
pre-filtered reaction list).

Because this codebase has no source of years of historical Indian-equity
headlines (`app.news.client.NewsClient`'s two providers are recent-
window only -- see the implementation assessment), `historical_event_stats`
will be empty for a long time after this subsystem ships. Every
event-specific feature below is `None` in that case, not a fabricated
0.0 -- `app.forecasting.ml.pipeline` must treat a `None` news feature as
"exclude from the model," not "no news effect."
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.forecasting.ml.news.event_study import EventStatistics
from app.forecasting.ml.news.models import EventType, NewsEvent, Sentiment
from app.forecasting.ml.news.timing import MarketTiming


@dataclass(frozen=True)
class NewsFeatures:
    news_count_1d: int = 0
    news_count_7d: int = 0
    positive_news_count_7d: int = 0
    negative_news_count_7d: int = 0
    avg_sentiment_7d: float | None = None
    weighted_sentiment_7d: float | None = None  # weighted by importance_score
    high_impact_news_count_7d: int = 0
    max_novelty_1d: float | None = None
    most_recent_event_type: EventType | None = None
    most_recent_event_days_ago: float | None = None
    historical_event_success_rate: dict[str, float] = field(default_factory=dict)  # event_type -> positive_rate (14d)
    event_14d_expected_return: float | None = None
    event_30d_expected_return: float | None = None
    post_market_event_flag: bool = False
    data_available: bool = False


def build_news_features(
    *,
    as_of: datetime,
    events_as_of: list[NewsEvent],
    historical_event_stats: dict[EventType, EventStatistics],
) -> NewsFeatures:
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    window_1d = [e for e in events_as_of if as_of - e.published_at <= timedelta(days=1)]
    window_7d = [e for e in events_as_of if as_of - e.published_at <= timedelta(days=7)]

    if not events_as_of:
        return NewsFeatures(data_available=False)

    positive_7d = [e for e in window_7d if e.sentiment == Sentiment.POSITIVE]
    negative_7d = [e for e in window_7d if e.sentiment == Sentiment.NEGATIVE]
    high_impact_7d = [e for e in window_7d if e.importance_score >= 0.7]

    avg_sentiment_7d = None
    weighted_sentiment_7d = None
    if window_7d:
        avg_sentiment_7d = sum(e.sentiment_score for e in window_7d) / len(window_7d)
        total_importance = sum(e.importance_score for e in window_7d)
        if total_importance > 0:
            weighted_sentiment_7d = sum(e.sentiment_score * e.importance_score for e in window_7d) / total_importance

    max_novelty_1d = max((e.novelty_score for e in window_1d), default=None)

    most_recent = max(events_as_of, key=lambda e: e.published_at, default=None)
    most_recent_event_type = most_recent.event_type if most_recent else None
    most_recent_days_ago = (as_of - most_recent.published_at).total_seconds() / 86400 if most_recent else None

    success_rate: dict[str, float] = {}
    event_14d_expected_return = None
    event_30d_expected_return = None
    if most_recent is not None and most_recent_days_ago is not None and most_recent_days_ago <= 30:
        stats = historical_event_stats.get(most_recent.event_type)
        if stats is not None and stats.is_reliable:
            if "return_14d" in stats.positive_rate_by_horizon:
                success_rate[f"historical_{most_recent.event_type.value}_14d"] = stats.positive_rate_by_horizon["return_14d"]
                event_14d_expected_return = stats.median_return_by_horizon.get("return_14d")
            if "return_30d" in stats.positive_rate_by_horizon:
                success_rate[f"historical_{most_recent.event_type.value}_30d"] = stats.positive_rate_by_horizon["return_30d"]
                event_30d_expected_return = stats.median_return_by_horizon.get("return_30d")

    post_market_flag = bool(window_1d) and any(e.market_timing == MarketTiming.POST_MARKET for e in window_1d)

    return NewsFeatures(
        news_count_1d=len(window_1d),
        news_count_7d=len(window_7d),
        positive_news_count_7d=len(positive_7d),
        negative_news_count_7d=len(negative_7d),
        avg_sentiment_7d=avg_sentiment_7d,
        weighted_sentiment_7d=weighted_sentiment_7d,
        high_impact_news_count_7d=len(high_impact_7d),
        max_novelty_1d=max_novelty_1d,
        most_recent_event_type=most_recent_event_type,
        most_recent_event_days_ago=most_recent_days_ago,
        historical_event_success_rate=success_rate,
        event_14d_expected_return=event_14d_expected_return,
        event_30d_expected_return=event_30d_expected_return,
        post_market_event_flag=post_market_flag,
        data_available=True,
    )
