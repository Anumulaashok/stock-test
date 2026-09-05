"""Novelty scoring (spec section 13): repeated coverage of the same
underlying story should score lower than the first report of it.

Uses headline text similarity (no ML model needed) against the same
ticker's recent events -- a follow-up article re-reporting the same
event a few hours later shares most of its headline vocabulary with the
original; an unrelated new event does not. This is intentionally coarse;
a real surprise/expected-vs-actual novelty signal (spec section 13's
second half) needs analyst-consensus data this codebase has no source
for today, so `estimate_surprise` below returns `None` rather than
inventing an expectation.
"""

from datetime import timedelta
from difflib import SequenceMatcher

from app.forecasting.ml.news.models import NewsEvent

_NOVELTY_WINDOW = timedelta(hours=48)
_SIMILARITY_THRESHOLD = 0.6


def compute_novelty_score(current: NewsEvent, recent_same_ticker_events: list[NewsEvent]) -> float:
    """1.0 = no similar prior coverage found; lower values mean a more
    similar, more recent prior article existed. `recent_same_ticker_events`
    should already be filtered to the same ticker, sorted by
    `published_at` descending, does not need to be pre-filtered by time
    window (this function applies `_NOVELTY_WINDOW` itself)."""
    best_similarity = 0.0
    for prior in recent_same_ticker_events:
        if prior.published_at >= current.published_at:
            continue
        age = current.published_at - prior.published_at
        if age > _NOVELTY_WINDOW:
            continue
        similarity = SequenceMatcher(None, current.headline.lower(), prior.headline.lower()).ratio()
        if prior.event_type == current.event_type:
            similarity = max(similarity, _SIMILARITY_THRESHOLD if similarity > 0.3 else similarity)
        best_similarity = max(best_similarity, similarity)

    return max(1.0 - best_similarity, 0.0)


def estimate_surprise(*, expected: float | None, actual: float | None) -> float | None:
    """`(actual - expected) / abs(expected)` when both are known (e.g. an
    earnings-beat headline that states a consensus estimate); `None`
    when no reliable expectation is available -- per spec section 13,
    "Do not invent expected values when no reliable expectation data
    exists," this is the only path that ever produces a surprise value."""
    if expected is None or actual is None or expected == 0:
        return None
    return (actual - expected) / abs(expected)
