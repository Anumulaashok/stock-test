"""Pluggable news-event classifier (spec section 9).

`EventClassifier` is the interface; `KeywordEventClassifier` is the
default implementation -- deliberately simple (substring/keyword rules
over the headline+summary) so it needs no model download or GPU and
degrades transparently (low `importance_score`, `EventType.OTHER`) when
nothing matches, rather than guessing. Swapping in a real financial NLP
model (FinBERT or similar) means implementing this same interface and
changing one line in `app.forecasting.ml.news.pipeline` wiring -- no
change to the event-study or feature code that consumes `NewsEvent`.

No existing LLM/news-classification mechanism in this codebase covers
event typing (the Finnhub research pipeline and `app.news.client` both
surface raw headlines only -- see `app.forecasting.ml.news.models`
docstring), so there is nothing to reuse here beyond the interface
shape itself.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.forecasting.ml.news.models import EventType, Sentiment

_POSITIVE_WORDS = ("beat", "surge", "rally", "record", "wins", "won", "profit rise", "upgrade", "outperform", "strong")
_NEGATIVE_WORDS = ("miss", "falls", "fall", "plunge", "loss", "downgrade", "probe", "fraud", "default", "weak", "cuts")

_EVENT_KEYWORDS: dict[EventType, tuple[str, ...]] = {
    EventType.EARNINGS_BEAT: ("beats estimates", "profit beats", "q1 beat", "q2 beat", "q3 beat", "q4 beat"),
    EventType.EARNINGS_MISS: ("misses estimates", "profit misses", "below estimates"),
    EventType.EARNINGS: ("quarterly results", "q1 results", "q2 results", "q3 results", "q4 results", "net profit", "earnings"),
    EventType.ORDER_WIN: ("wins order", "bags order", "secures order", "wins contract", "bags contract"),
    EventType.ORDER_LOSS: ("loses order", "loses contract", "order cancelled"),
    EventType.CONTRACT: ("signs contract", "contract with", "agreement with"),
    EventType.NEW_PRODUCT: ("launches", "unveils", "new product", "new launch"),
    EventType.CAPEX: ("capex", "capital expenditure", "invests in plant"),
    EventType.EXPANSION: ("expansion", "new plant", "new facility", "expands capacity"),
    EventType.ACQUISITION: ("acquires", "acquisition of", "to acquire"),
    EventType.MERGER: ("merger", "to merge", "amalgamation"),
    EventType.MANAGEMENT_CHANGE: ("resigns", "appoints", "steps down", "new ceo", "new cfo", "new md"),
    EventType.PROMOTER_ACTIVITY: ("promoter stake", "promoter pledge", "promoter sells", "promoter buys"),
    EventType.INSIDER_ACTIVITY: ("insider trading", "insider buys", "insider sells"),
    EventType.FUND_RAISE: ("raises funds", "qip", "rights issue", "preferential allotment", "fund raise"),
    EventType.DEBT: ("debt", "bond issue", "ncd issue", "credit rating"),
    EventType.DIVIDEND: ("dividend",),
    EventType.BUYBACK: ("buyback", "share buyback"),
    EventType.REGULATORY: ("sebi", "rbi notice", "regulatory approval", "compliance"),
    EventType.LEGAL: ("lawsuit", "litigation", "court", "legal notice"),
    EventType.GOVERNMENT_POLICY: ("government policy", "tariff", "import duty", "export ban", "budget"),
    EventType.BROKERAGE: ("brokerage", "target price", "maintains buy", "maintains sell"),
    EventType.RATING_CHANGE: ("upgrades rating", "downgrades rating", "rating upgraded", "rating downgraded"),
    EventType.GUIDANCE: ("guidance", "outlook raised", "outlook cut"),
    EventType.CUSTOMER_WIN: ("new client", "new customer", "partners with"),
    EventType.CUSTOMER_LOSS: ("loses client", "loses customer", "client exits"),
    EventType.PLANT_SHUTDOWN: ("plant shutdown", "halts production", "shuts plant"),
    EventType.FRAUD: ("fraud", "scam", "embezzlement"),
    EventType.ACCOUNTING: ("accounting irregularities", "restates", "auditor resigns"),
    EventType.SECTOR_EVENT: ("sector outlook", "industry body"),
    EventType.MACRO: ("inflation", "gdp", "interest rate", "rbi policy", "fed rate"),
}


@dataclass(frozen=True)
class ClassificationResult:
    event_type: EventType
    sentiment: Sentiment
    sentiment_score: float
    importance_score: float


class EventClassifier(ABC):
    @abstractmethod
    def classify(self, headline: str, summary: str | None = None) -> ClassificationResult: ...


class KeywordEventClassifier(EventClassifier):
    def classify(self, headline: str, summary: str | None = None) -> ClassificationResult:
        text = f"{headline} {summary or ''}".lower()

        event_type = EventType.OTHER
        for candidate_type, keywords in _EVENT_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                event_type = candidate_type
                break

        positive_hits = sum(1 for word in _POSITIVE_WORDS if word in text)
        negative_hits = sum(1 for word in _NEGATIVE_WORDS if word in text)
        net = positive_hits - negative_hits
        if net > 0:
            sentiment = Sentiment.POSITIVE
        elif net < 0:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.NEUTRAL
        sentiment_score = max(min(net / 3.0, 1.0), -1.0)

        importance_score = 0.3 if event_type == EventType.OTHER else 0.6
        if event_type in (EventType.EARNINGS_BEAT, EventType.EARNINGS_MISS, EventType.FRAUD, EventType.ACQUISITION, EventType.MERGER):
            importance_score = 0.85

        return ClassificationResult(
            event_type=event_type, sentiment=sentiment, sentiment_score=sentiment_score,
            importance_score=importance_score,
        )
