from app.search.service import StockSearchService


def test_empty_query_returns_no_results():
    assert StockSearchService().search("") == []
    assert StockSearchService().search("   ") == []


def test_exact_symbol_match_ranks_first():
    results = StockSearchService().search("TCS")
    assert results[0].symbol == "TCS"
    assert results[0].name == "Tata Consultancy Services Limited"
    assert results[0].exchange == "NSE"
    assert results[0].isin == "INE467B01029"


def test_symbol_prefix_match():
    results = StockSearchService().search("RELIA")
    assert any(r.symbol == "RELIANCE" for r in results)


def test_search_by_company_name_is_case_insensitive():
    results = StockSearchService().search("infosys")
    assert any(r.symbol == "INFY" for r in results)


def test_unknown_query_returns_empty_list():
    assert StockSearchService().search("ZZZZZZNOTATICKERZZZZZZ") == []


def test_limit_is_respected():
    results = StockSearchService().search("A", limit=3)
    assert len(results) <= 3


def test_results_are_deduplicated_by_rank_bucket():
    # A query matching many different rank buckets should never return
    # the same symbol twice.
    results = StockSearchService().search("TA", limit=25)
    symbols = [r.symbol for r in results]
    assert len(symbols) == len(set(symbols))
