"""Local stock-symbol search/autocomplete.

Matches against a static NSE equity list bundled at
`app/data/static/nse_equity_list.csv` — entirely in-memory, no network
call, no external provider dependency.

Why local rather than a provider API: IndianAPI (stock.indianapi.in)
exposes a `/search?query=` endpoint, but it was live-verified to return
`{"results": [], "count": 0}` for every query on the current (free)
tier/key — confirmed non-functional, not a param-naming issue. FMP has
no Indian-equity search coverage at all. A bundled dataset works
immediately, costs nothing per keystroke, and needs no API key.

Data provenance: sourced from NSE's own public equity listing
(archives.nseindia.com/content/equities/EQUITY_L.csv) — a well-known
public dataset, not scraped from a UI and not fabricated. It will drift
out of date as NSE lists/delists companies; refreshing it is a data
update, not a code change.
"""

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.models.search import StockSearchResult

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "static" / "nse_equity_list.csv"


@dataclass(frozen=True)
class _Entry:
    symbol: str
    name: str
    isin: str | None


@lru_cache
def _load_entries() -> tuple[_Entry, ...]:
    entries: list[_Entry] = []
    with _DATA_FILE.open(newline="", encoding="utf-8") as f:
        # NSE's published CSV has inconsistent header whitespace (e.g.
        # " ISIN NUMBER" with a leading space) -- normalize keys rather
        # than depend on exact spacing.
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip()
            name = (row.get("NAME OF COMPANY") or "").strip()
            isin = (row.get("ISIN NUMBER") or "").strip() or None
            if symbol and name:
                entries.append(_Entry(symbol=symbol, name=name, isin=isin))
    return tuple(entries)


class StockSearchService:
    """Ranks the local equity list against a free-text query.

    Ranking (best first): exact symbol match, symbol starts-with,
    symbol contains, company name starts-with, company name contains.
    Matching is case-insensitive throughout.
    """

    def search(self, query: str, limit: int = 10) -> list[StockSearchResult]:
        q = query.strip()
        if not q:
            return []
        q_upper = q.upper()
        q_fold = q.casefold()

        exact: _Entry | None = None
        symbol_prefix: list[_Entry] = []
        symbol_contains: list[_Entry] = []
        name_prefix: list[_Entry] = []
        name_contains: list[_Entry] = []

        for entry in _load_entries():
            if entry.symbol == q_upper:
                exact = entry
            elif entry.symbol.startswith(q_upper):
                symbol_prefix.append(entry)
            elif q_upper in entry.symbol:
                symbol_contains.append(entry)
            elif entry.name.casefold().startswith(q_fold):
                name_prefix.append(entry)
            elif q_fold in entry.name.casefold():
                name_contains.append(entry)

        ranked = (
            ([exact] if exact else [])
            + symbol_prefix
            + symbol_contains
            + name_prefix
            + name_contains
        )
        return [
            StockSearchResult(symbol=e.symbol, name=e.name, isin=e.isin)
            for e in ranked[:limit]
        ]
