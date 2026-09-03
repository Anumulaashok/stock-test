from decimal import Decimal

from app.data.mappers.screener import map_screener_chart, map_screener_company_list


def d(value) -> Decimal:
    return Decimal(str(value))


_RAW = {
    "datasets": [
        {
            "metric": "Price", "label": "Price on NSE",
            "values": [["2026-09-02", "178.35"], ["2026-09-03", "181.07"]],
        },
        {
            "metric": "DMA50", "label": "50 DMA",
            "values": [["2026-09-02", "194.57"], ["2026-09-03", "194.04"]],
        },
        {
            "metric": "DMA200", "label": "200 DMA",
            "values": [["2026-09-02", "203.12"], ["2026-09-03", "202.90"]],
        },
        {
            "metric": "Volume", "label": "Volume",
            "values": [
                ["2026-09-02", 1715099, {"delivery": 50}],
                ["2026-09-03", 5698964, {"delivery": None}],
            ],
        },
    ]
}


def test_maps_price_dma_and_volume_per_date():
    rows = map_screener_chart(_RAW)
    by_date = {r["date"]: r for r in rows}

    assert by_date["2026-09-03"]["price"] == d("181.07")
    assert by_date["2026-09-03"]["dma50"] == d("194.04")
    assert by_date["2026-09-03"]["dma200"] == d("202.90")
    assert by_date["2026-09-03"]["volume"] == d(5698964)


def test_missing_delivery_percentage_stays_none():
    rows = map_screener_chart(_RAW)
    by_date = {r["date"]: r for r in rows}
    assert by_date["2026-09-03"]["delivery_percentage"] is None
    assert by_date["2026-09-02"]["delivery_percentage"] == d(50)


def test_tolerates_missing_datasets():
    assert map_screener_chart({}) == []
    assert map_screener_chart({"datasets": []}) == []


def test_tolerates_a_date_present_in_only_one_series():
    raw = {
        "datasets": [
            {"metric": "Price", "values": [["2026-09-03", "181.07"]]},
            {"metric": "Volume", "values": [["2026-09-04", 100, {}]]},
        ]
    }
    rows = map_screener_chart(raw)
    by_date = {r["date"]: r for r in rows}
    assert by_date["2026-09-03"]["price"] == d("181.07")
    assert by_date["2026-09-03"]["volume"] is None
    assert by_date["2026-09-04"]["volume"] == d(100)
    assert by_date["2026-09-04"]["price"] is None


# --- map_screener_company_list --------------------------------------------------------

# Real user-supplied Screener company-search result shape (2026-09-03).
_COMPANY_SEARCH_RAW = [
    {"id": 681, "name": "Coal India Ltd", "url": "/company/COALINDIA/consolidated/"},
    {"id": 2262, "name": "Coforge Ltd", "url": "/company/COFORGE/consolidated/"},
    {"id": 685, "name": "Colgate-Palmolive (India) Ltd", "url": "/company/COLPAL/"},
    {"id": None, "name": "Search everywhere: co", "url": "/full-text-search/?q=co"},
]


def test_company_list_maps_ticker_from_url():
    rows = map_screener_company_list(_COMPANY_SEARCH_RAW)
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["COALINDIA"]["screener_company_id"] == 681
    assert by_ticker["COALINDIA"]["company_name"] == "Coal India Ltd"
    assert by_ticker["COFORGE"]["screener_company_id"] == 2262


def test_company_list_marks_consolidated_from_url_suffix():
    rows = map_screener_company_list(_COMPANY_SEARCH_RAW)
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["COALINDIA"]["consolidated"] is True
    assert by_ticker["COLPAL"]["consolidated"] is False


def test_company_list_skips_null_id_sentinel_row():
    rows = map_screener_company_list(_COMPANY_SEARCH_RAW)
    tickers = {r["ticker"] for r in rows}
    assert len(rows) == 3
    assert "co" not in tickers


def test_company_list_skips_entries_with_unparseable_url():
    rows = map_screener_company_list([{"id": 1, "name": "X", "url": "/full-text-search/?q=x"}])
    assert rows == []


def test_company_list_tolerates_non_list_input():
    assert map_screener_company_list(None) == []
    assert map_screener_company_list({}) == []
