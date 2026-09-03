"""Unit tests for `SectorRankingService` against a fake
`AnalysisApplicationService` -- no HTTP, no real provider calls. Verifies
the sector score is the average of constituents' `overall_score`, that a
failed/unavailable ticker is excluded from the average rather than
treated as zero, and that ranking sorts sectors by score descending.
"""

from decimal import Decimal

import pytest

from app.models.scoring import CategoryScore, ScoreBand, ScoreStatus, ScoringResult
from app.pipeline.models import CombinedAnalysisResult, PipelineCompanyInfo, PipelineStatus
from app.sectors.service import SectorRankingService


def _scoring(overall: Decimal, risk: Decimal = Decimal(80), growth: Decimal = Decimal(60)) -> ScoringResult:
    return ScoringResult(
        company_name="Test Co",
        overall_score=overall,
        overall_status=ScoreStatus.CALCULATED,
        band=ScoreBand.GOOD,
        category_scores=[
            CategoryScore(category="risk", score=risk, weight=Decimal(20), status=ScoreStatus.CALCULATED),
            CategoryScore(category="growth", score=growth, weight=Decimal(20), status=ScoreStatus.CALCULATED),
        ],
    )


def _result(ticker: str, overall: Decimal | None, failed: bool = False) -> CombinedAnalysisResult:
    if failed or overall is None:
        return CombinedAnalysisResult(
            company=PipelineCompanyInfo(name=ticker, ticker=ticker),
            status=PipelineStatus.FAILED,
            warnings=["no data"],
        )
    return CombinedAnalysisResult(
        company=PipelineCompanyInfo(name=ticker, ticker=ticker),
        status=PipelineStatus.CALCULATED,
        scoring=_scoring(overall),
    )


class FakeApplicationService:
    def __init__(self, results: dict[str, CombinedAnalysisResult]) -> None:
        self._results = results
        self.calls: list[str] = []

    async def analyze_by_ticker(self, request, run_analyst: bool = True) -> CombinedAnalysisResult:
        self.calls.append(request.ticker)
        return self._results[request.ticker]


@pytest.mark.asyncio
async def test_sector_score_averages_constituent_overall_scores():
    fake = FakeApplicationService(
        {"AAA": _result("AAA", Decimal(80)), "BBB": _result("BBB", Decimal(60))}
    )
    service = SectorRankingService(fake)

    result = await service.rank_sectors({"Test Sector": ["AAA", "BBB"]})

    assert result.status == "success"
    assert len(result.sectors) == 1
    sector = result.sectors[0]
    assert sector.sector_score == Decimal("70.0")
    assert sector.constituents_evaluated == 2
    assert sector.constituents_total == 2


@pytest.mark.asyncio
async def test_failed_ticker_excluded_from_average_not_treated_as_zero():
    fake = FakeApplicationService(
        {"AAA": _result("AAA", Decimal(80)), "BBB": _result("BBB", None, failed=True)}
    )
    service = SectorRankingService(fake)

    result = await service.rank_sectors({"Test Sector": ["AAA", "BBB"]})

    sector = result.sectors[0]
    # If the failed ticker were treated as 0, this would be 40.0, not 80.0.
    assert sector.sector_score == Decimal("80.0")
    assert sector.constituents_evaluated == 1
    assert sector.constituents_total == 2


@pytest.mark.asyncio
async def test_sectors_ranked_by_score_descending():
    fake = FakeApplicationService(
        {
            "LOW1": _result("LOW1", Decimal(40)),
            "HIGH1": _result("HIGH1", Decimal(90)),
        }
    )
    service = SectorRankingService(fake)

    result = await service.rank_sectors({"Weak Sector": ["LOW1"], "Strong Sector": ["HIGH1"]})

    assert [s.sector for s in result.sectors] == ["Strong Sector", "Weak Sector"]


@pytest.mark.asyncio
async def test_all_constituents_failed_marks_sector_unavailable_but_no_crash():
    fake = FakeApplicationService({"AAA": _result("AAA", None, failed=True)})
    service = SectorRankingService(fake)

    result = await service.rank_sectors({"Empty Sector": ["AAA"]})

    sector = result.sectors[0]
    assert sector.sector_score is None
    assert sector.constituents_evaluated == 0
    assert any("Empty Sector" in w for w in result.warnings)
