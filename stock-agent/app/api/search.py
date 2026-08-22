"""Stock search/autocomplete endpoint.

Served entirely from a local, static dataset (`app/search/service.py`)
— no external API call, no per-keystroke cost, no key required.
"""

from fastapi import APIRouter, Query

from app.models.search import StockSearchResult
from app.search.service import StockSearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])

_service = StockSearchService()


@router.get("")
async def search_stocks(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=25),
) -> list[StockSearchResult]:
    """Suggests NSE-listed companies matching `q` by symbol or name."""
    return _service.search(q, limit=limit)
