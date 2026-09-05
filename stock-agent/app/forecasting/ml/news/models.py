"""News-event domain models (spec sections 8/9).

`NewsEvent` is the normalized shape every classified news item is stored
as (see `app.db.models.NewsEventRow` for the persisted form). Two "news"
subsystems already exist in this codebase and must not be conflated: the
Finnhub-backed `app.research` pipeline (analyst research citations) and
`app.news.client.NewsClient` (newsdata.io/newsapi.org headline search,
today used only for a sector headline count). `NewsEvent` is a third,
purpose-built shape for return prediction -- built from whichever
`NewsClient` results are available at ingestion time, but independent of
either existing model so this subsystem's schema can evolve without
touching them.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class EventType(StrEnum):
    EARNINGS = "EARNINGS"
    EARNINGS_BEAT = "EARNINGS_BEAT"
    EARNINGS_MISS = "EARNINGS_MISS"
    ORDER_WIN = "ORDER_WIN"
    ORDER_LOSS = "ORDER_LOSS"
    CONTRACT = "CONTRACT"
    NEW_PRODUCT = "NEW_PRODUCT"
    CAPEX = "CAPEX"
    EXPANSION = "EXPANSION"
    ACQUISITION = "ACQUISITION"
    MERGER = "MERGER"
    MANAGEMENT_CHANGE = "MANAGEMENT_CHANGE"
    PROMOTER_ACTIVITY = "PROMOTER_ACTIVITY"
    INSIDER_ACTIVITY = "INSIDER_ACTIVITY"
    FUND_RAISE = "FUND_RAISE"
    DEBT = "DEBT"
    DIVIDEND = "DIVIDEND"
    BUYBACK = "BUYBACK"
    REGULATORY = "REGULATORY"
    LEGAL = "LEGAL"
    GOVERNMENT_POLICY = "GOVERNMENT_POLICY"
    BROKERAGE = "BROKERAGE"
    RATING_CHANGE = "RATING_CHANGE"
    GUIDANCE = "GUIDANCE"
    CUSTOMER_WIN = "CUSTOMER_WIN"
    CUSTOMER_LOSS = "CUSTOMER_LOSS"
    PLANT_SHUTDOWN = "PLANT_SHUTDOWN"
    FRAUD = "FRAUD"
    ACCOUNTING = "ACCOUNTING"
    SECTOR_EVENT = "SECTOR_EVENT"
    MACRO = "MACRO"
    OTHER = "OTHER"


class Sentiment(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class MarketTiming(StrEnum):
    PRE_MARKET = "PRE_MARKET"
    MARKET_HOURS = "MARKET_HOURS"
    POST_MARKET = "POST_MARKET"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"
    UNKNOWN = "UNKNOWN"


class NewsEvent(BaseModel):
    ticker: str
    company: str | None = None
    published_at: datetime  # must be timezone-aware
    source: str | None = None
    headline: str
    summary: str | None = None
    url: str | None = None
    event_type: EventType = EventType.OTHER
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0  # -1..1
    importance_score: float = 0.5  # 0..1
    novelty_score: float = 1.0  # 0..1, 1 = first report of this story
    market_timing: MarketTiming = MarketTiming.UNKNOWN


class EventReaction(BaseModel):
    """One event's measured stock reaction -- computed by
    `app.forecasting.ml.news.event_study`, never fabricated when price
    data around the event date is unavailable (fields stay `None`)."""

    event_id: str
    ticker: str
    reaction_session_date: str | None  # ISO date of the session the market could first react in
    return_same_day: float | None = None
    return_1d: float | None = None
    return_3d: float | None = None
    return_5d: float | None = None
    return_14d: float | None = None
    return_30d: float | None = None
    abnormal_return_5d: float | None = None
    volume_change_5d: float | None = None
    volatility_change_5d: float | None = None
    max_drawdown_after: float | None = None
    max_gain_after: float | None = None
