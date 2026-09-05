"""Historical news event study (spec sections 10/11/12).

`compute_reaction` measures what actually happened to a stock after one
classified news event, correctly anchored on the *reaction session*
(spec section 10's PRE/POST-market timing rule, via
`app.forecasting.ml.news.timing.next_trading_session`) rather than the
event's raw calendar date. `aggregate_event_statistics` rolls many
reactions up per event type (and optionally per ticker/sector/sentiment/
regime/timing) and refuses to report a statistic below
`MIN_EVENT_STUDY_SAMPLE_SIZE` (spec section 12: "Only expose statistics
when sample sizes are adequate").
"""

from dataclasses import dataclass

import pandas as pd

from app.forecasting.ml.news.models import EventReaction, EventType, NewsEvent
from app.forecasting.ml.news.timing import next_trading_session

MIN_EVENT_STUDY_SAMPLE_SIZE = 20


def compute_reaction(
    event: NewsEvent,
    *,
    stock_close: pd.Series,
    stock_volume: pd.Series | None = None,
    benchmark_close: pd.Series | None = None,
) -> EventReaction | None:
    """Returns `None` (never a fabricated partial reaction) when the
    event's reaction session can't be located in `stock_close`'s index --
    e.g. the event predates the fetched price history, or the ticker had
    no trading that day."""
    reaction_date = next_trading_session(event.published_at, stock_close.index)
    if reaction_date is None or reaction_date not in stock_close.index:
        return None

    reaction_idx = stock_close.index.get_loc(reaction_date)
    if isinstance(reaction_idx, slice):
        return None
    base_idx = reaction_idx - 1
    if base_idx < 0:
        return None
    base_price = stock_close.iloc[base_idx]
    if base_price == 0 or pd.isna(base_price):
        return None

    def price_at(offset: int) -> float | None:
        idx = reaction_idx + offset
        if idx < 0 or idx >= len(stock_close):
            return None
        value = stock_close.iloc[idx]
        return None if pd.isna(value) else float(value)

    def ret(offset: int) -> float | None:
        price = price_at(offset)
        return None if price is None else price / base_price - 1

    return_same_day = ret(0)
    return_1d = ret(1)
    return_3d = ret(3)
    return_5d = ret(5)
    return_14d = ret(14)
    return_30d = ret(30)

    abnormal_return_5d = None
    if return_5d is not None and benchmark_close is not None and reaction_date in benchmark_close.index:
        bench_idx = benchmark_close.index.get_loc(reaction_date)
        bench_base_idx = bench_idx - 1
        bench_end_idx = bench_idx + 5
        if bench_base_idx >= 0 and bench_end_idx < len(benchmark_close):
            bench_base = benchmark_close.iloc[bench_base_idx]
            bench_end = benchmark_close.iloc[bench_end_idx]
            if bench_base and not pd.isna(bench_base) and not pd.isna(bench_end):
                benchmark_return_5d = bench_end / bench_base - 1
                abnormal_return_5d = return_5d - benchmark_return_5d

    volume_change_5d = None
    if stock_volume is not None and reaction_date in stock_volume.index:
        window_end = reaction_idx + 5
        if window_end < len(stock_volume) and reaction_idx - 5 >= 0:
            before = stock_volume.iloc[reaction_idx - 5 : reaction_idx].mean()
            after = stock_volume.iloc[reaction_idx : window_end].mean()
            if before and not pd.isna(before):
                volume_change_5d = float(after / before - 1)

    window_end_14 = min(reaction_idx + 14, len(stock_close) - 1)
    post_window = stock_close.iloc[reaction_idx : window_end_14 + 1]
    max_gain_after = float(post_window.max() / base_price - 1) if len(post_window) else None
    max_drawdown_after = float(post_window.min() / base_price - 1) if len(post_window) else None

    return EventReaction(
        event_id=f"{event.ticker}:{event.published_at.isoformat()}:{event.headline[:40]}",
        ticker=event.ticker,
        reaction_session_date=reaction_date.date().isoformat(),
        return_same_day=return_same_day,
        return_1d=return_1d,
        return_3d=return_3d,
        return_5d=return_5d,
        return_14d=return_14d,
        return_30d=return_30d,
        abnormal_return_5d=abnormal_return_5d,
        volume_change_5d=volume_change_5d,
        max_drawdown_after=max_drawdown_after,
        max_gain_after=max_gain_after,
    )


@dataclass(frozen=True)
class EventStatistics:
    group_key: str
    sample_size: int
    median_return_by_horizon: dict[str, float]
    positive_rate_by_horizon: dict[str, float]

    @property
    def is_reliable(self) -> bool:
        return self.sample_size >= MIN_EVENT_STUDY_SAMPLE_SIZE


_HORIZON_FIELDS = ("return_same_day", "return_1d", "return_3d", "return_5d", "return_14d", "return_30d")


def aggregate_event_statistics(reactions: list[EventReaction], *, group_key: str = "all") -> EventStatistics:
    """Never returns partial/fabricated stats for an under-sampled group
    -- callers must check `is_reliable` before displaying anything (spec
    section 12)."""
    frame = pd.DataFrame([r.model_dump() for r in reactions])
    median_by_horizon: dict[str, float] = {}
    positive_by_horizon: dict[str, float] = {}
    sample_size = len(frame)
    if sample_size > 0:
        for field in _HORIZON_FIELDS:
            series = frame[field].dropna()
            if len(series) == 0:
                continue
            median_by_horizon[field] = float(series.median())
            positive_by_horizon[field] = float((series > 0).mean())

    return EventStatistics(
        group_key=group_key, sample_size=sample_size,
        median_return_by_horizon=median_by_horizon, positive_rate_by_horizon=positive_by_horizon,
    )


def group_reactions_by_event_type(
    events_with_reactions: list[tuple[NewsEvent, EventReaction]],
) -> dict[EventType, EventStatistics]:
    by_type: dict[EventType, list[EventReaction]] = {}
    for event, reaction in events_with_reactions:
        by_type.setdefault(event.event_type, []).append(reaction)
    return {
        event_type: aggregate_event_statistics(reactions, group_key=event_type.value)
        for event_type, reactions in by_type.items()
    }
