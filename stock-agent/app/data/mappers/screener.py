"""Maps Screener.in's `/chart` API response into plain per-date dicts
ready for `app.data.daily_price_history_service.upsert_daily_price`.
Pure functions only — no HTTP.

Response shape, verified from a real user-supplied dump (2026-09-03):

    {"datasets": [
        {"metric": "Price", "label": "Price on NSE", "values": [["2026-09-03", "181.07"], ...]},
        {"metric": "DMA50", "label": "50 DMA", "values": [["2026-09-03", "194.04"], ...]},
        {"metric": "DMA200", "label": "200 DMA", "values": [["2026-09-03", "202.90"], ...]},
        {"metric": "Volume", "label": "Volume", "values": [["2026-09-03", 5698964, {"delivery": 45}], ...]}
    ]}

Dates are already `"YYYY-MM-DD"` — no period-label conversion needed
(unlike IndianAPI's `"Mon YYYY"` convention). Each dataset is a
sparse/independent series over dates; this merges them into one row per
date, tolerating a date present in one series but missing from another.
"""

from decimal import Decimal, InvalidOperation


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _series(datasets: list, metric_name: str) -> list:
    dataset = next((d for d in datasets if isinstance(d, dict) and d.get("metric") == metric_name), None)
    values = dataset.get("values") if isinstance(dataset, dict) else None
    return values if isinstance(values, list) else []


def map_screener_chart(raw: dict) -> list[dict]:
    datasets = raw.get("datasets")
    if not isinstance(datasets, list):
        return []

    by_date: dict[str, dict] = {}

    for entry in _series(datasets, "Price"):
        if not isinstance(entry, list) or len(entry) < 2 or not isinstance(entry[0], str):
            continue
        by_date.setdefault(entry[0], {})["price"] = _to_decimal(entry[1])

    for metric_name, field in (("DMA50", "dma50"), ("DMA200", "dma200")):
        for entry in _series(datasets, metric_name):
            if not isinstance(entry, list) or len(entry) < 2 or not isinstance(entry[0], str):
                continue
            by_date.setdefault(entry[0], {})[field] = _to_decimal(entry[1])

    for entry in _series(datasets, "Volume"):
        if not isinstance(entry, list) or len(entry) < 2 or not isinstance(entry[0], str):
            continue
        row = by_date.setdefault(entry[0], {})
        row["volume"] = _to_decimal(entry[1])
        meta = entry[2] if len(entry) > 2 and isinstance(entry[2], dict) else {}
        row["delivery_percentage"] = _to_decimal(meta.get("delivery"))

    return [
        {
            "date": date_str,
            "price": fields.get("price"),
            "dma50": fields.get("dma50"),
            "dma200": fields.get("dma200"),
            "volume": fields.get("volume"),
            "delivery_percentage": fields.get("delivery_percentage"),
        }
        for date_str, fields in by_date.items()
    ]


def _ticker_from_company_url(url: object) -> str | None:
    """Screener's own company-search results (e.g.
    `https://www.screener.in/api/company/search/?q=...`) return
    `{"id": ..., "name": ..., "url": "/company/COALINDIA/consolidated/"}`
    -- the ticker is the path segment right after `/company/`. A
    non-company URL (Screener's own "Search everywhere: ..." sentinel
    row uses `/full-text-search/?q=...`) has no such segment and yields
    `None`, same as a `null` id."""
    if not isinstance(url, str):
        return None
    parts = [segment for segment in url.strip("/").split("/") if segment]
    if len(parts) < 2 or parts[0] != "company":
        return None
    return parts[1].strip().upper() or None


def map_screener_company_list(raw: list) -> list[dict]:
    """Parses one of Screener's company-search JSON results (a plain
    list of `{id, name, url}` objects, `id` and/or `url` sometimes
    absent/null for a non-company row) into
    `[{ticker, company_name, screener_company_id, consolidated}, ...]`,
    ready for `app.data.screener_import_service.ScreenerImportService.register_company_mappings`.
    Skips any entry with a null/missing id or an unparseable url --
    never guesses a ticker or an id."""
    if not isinstance(raw, list):
        return []

    results: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        company_id = entry.get("id")
        if not isinstance(company_id, int):
            continue
        ticker = _ticker_from_company_url(entry.get("url"))
        if ticker is None:
            continue
        name = entry.get("name")
        results.append(
            {
                "ticker": ticker,
                "company_name": name if isinstance(name, str) and name.strip() else None,
                "screener_company_id": company_id,
                "consolidated": "consolidated" in (entry.get("url") or ""),
            }
        )
    return results
