"""Market Opportunity sector ranking.

Every score here comes straight from the app's own existing,
deterministic `ScoringService` output (`ScoringResult.overall_score`,
computed per ticker via the same `AnalysisApplicationService` the
single-ticker research flow already uses) — a sector's score is simply
the average of its constituents' `overall_score`. Nothing here is
LLM-computed. News (when a provider is configured) contributes only a
`news_headline_count` alongside the score, as context for the caller —
it never adjusts `sector_score` itself, so the ranking stays fully
deterministic and reproducible from the same underlying data.
"""

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.application.service import AnalysisApplicationService
from app.models.scoring import ScoreStatus
from app.models.sectors import MarketOpportunityResult, Outlook, RiskLevel, SectorStockSummary, SectorSummary
from app.news.client import NewsClient
from app.pipeline.models import PipelineStatus, ResearchOptions, TickerAnalysisRequest
from app.sectors.universe import SECTOR_UNIVERSE

logger = logging.getLogger(__name__)

_BULLISH_THRESHOLD = Decimal(70)
_BEARISH_THRESHOLD = Decimal(50)
_LOW_RISK_THRESHOLD = Decimal(70)
_MEDIUM_RISK_THRESHOLD = Decimal(40)
_TOP_STOCKS_PER_SECTOR = 3


def _outlook_for(score: Decimal | None) -> Outlook:
    if score is None:
        return Outlook.NEUTRAL
    if score >= _BULLISH_THRESHOLD:
        return Outlook.BULLISH
    if score < _BEARISH_THRESHOLD:
        return Outlook.BEARISH
    return Outlook.NEUTRAL


def _risk_for(risk_category_score: Decimal | None) -> RiskLevel:
    if risk_category_score is None:
        return RiskLevel.MEDIUM
    if risk_category_score >= _LOW_RISK_THRESHOLD:
        return RiskLevel.LOW
    if risk_category_score >= _MEDIUM_RISK_THRESHOLD:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


class SectorRankingService:
    def __init__(
        self,
        application_service: AnalysisApplicationService,
        news_client: NewsClient | None = None,
    ) -> None:
        self._application_service = application_service
        self._news_client = news_client

    async def _evaluate_ticker(
        self, ticker: str
    ) -> tuple[SectorStockSummary, Decimal | None, Decimal | None, Decimal | None] | None:
        try:
            result = await self._application_service.analyze_by_ticker(
                TickerAnalysisRequest(ticker=ticker, research=ResearchOptions(enabled=False)),
                run_analyst=False,
            )
        except Exception:
            logger.exception("Sector ranking: unexpected error evaluating %s", ticker)
            return None

        if result.status == PipelineStatus.FAILED or result.scoring is None:
            summary = SectorStockSummary(
                ticker=ticker,
                company_name=result.company.name,
                overall_score=None,
                band=None,
                status="unavailable",
            )
            return summary, None, None, None

        scoring = result.scoring
        summary = SectorStockSummary(
            ticker=ticker,
            company_name=scoring.company_name or result.company.name,
            overall_score=scoring.overall_score,
            band=scoring.band.value if scoring.band else None,
            status="calculated" if scoring.overall_status == ScoreStatus.CALCULATED else "unavailable",
        )
        by_category = {c.category: c.score for c in scoring.category_scores}
        return summary, by_category.get("risk"), by_category.get("growth"), by_category.get("valuation")

    @staticmethod
    def _category_score(stocks_raw: list, category: str) -> Decimal | None:
        values = [s for s in stocks_raw if s is not None]
        if not values:
            return None
        avg = sum(values) / Decimal(len(values))
        return avg.quantize(Decimal("0.1"))

    async def _score_sector(self, sector: str, tickers: list[str]) -> SectorSummary:
        evaluations = await asyncio.gather(*(self._evaluate_ticker(t) for t in tickers))
        evaluations = [e for e in evaluations if e is not None]

        summaries = [e[0] for e in evaluations]
        calculated = [s for s in summaries if s.overall_score is not None]
        risk_scores = [e[1] for e in evaluations if e[1] is not None]
        growth_scores = [e[2] for e in evaluations if e[2] is not None]
        valuation_scores = [e[3] for e in evaluations if e[3] is not None]

        sector_score = self._category_score([s.overall_score for s in calculated], "overall")
        risk_category_score = self._category_score(risk_scores, "risk")

        top_stocks = sorted(
            calculated, key=lambda s: s.overall_score or Decimal(0), reverse=True
        )[:_TOP_STOCKS_PER_SECTOR]

        news_count = 0
        if self._news_client is not None:
            news_result = await self._news_client.search(f"{sector} sector India stocks", limit=10)
            if news_result.status == "success":
                news_count = len(news_result.articles)

        return SectorSummary(
            sector=sector,
            sector_score=sector_score,
            outlook=_outlook_for(sector_score),
            risk=_risk_for(risk_category_score),
            growth_score=self._category_score(growth_scores, "growth"),
            valuation_score=self._category_score(valuation_scores, "valuation"),
            news_headline_count=news_count,
            constituents_evaluated=len(calculated),
            constituents_total=len(tickers),
            top_stocks=top_stocks,
        )

    async def rank_sectors(self, universe: dict[str, list[str]] | None = None) -> MarketOpportunityResult:
        universe = universe or SECTOR_UNIVERSE
        warnings: list[str] = []

        sector_summaries = await asyncio.gather(
            *(self._score_sector(sector, tickers) for sector, tickers in universe.items())
        )

        ranked = sorted(
            sector_summaries,
            key=lambda s: s.sector_score if s.sector_score is not None else Decimal(-1),
            reverse=True,
        )

        for sector in ranked:
            if sector.constituents_evaluated == 0:
                warnings.append(f"No constituents could be scored for {sector.sector}")

        status = "success" if any(s.sector_score is not None for s in ranked) else "unavailable"

        return MarketOpportunityResult(
            status=status,
            generated_at=datetime.now(UTC).isoformat(),
            sectors=ranked,
            warnings=warnings,
        )
