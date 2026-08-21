from app.models.research import SourceType
from app.research.mappers.finnhub import map_articles


def article(**overrides):
    record = {
        "category": "company",
        "datetime": 1735689600,  # 2025-01-01T00:00:00Z
        "headline": "Acme Corp announces expansion",
        "id": 1,
        "related": "ACME",
        "source": "marketwatch",
        "summary": "Acme Corp is expanding into new markets.",
        "url": "https://www.marketwatch.com/story/acme-expands",
    }
    record.update(overrides)
    return record


def test_complete_article_maps_all_fields():
    items, warnings = map_articles([article()])
    assert warnings == []
    assert len(items) == 1
    item = items[0]
    assert item.title == "Acme Corp announces expansion"
    assert item.summary == "Acme Corp is expanding into new markets."
    assert item.source.publisher == "marketwatch"
    assert item.source.url == "https://www.marketwatch.com/story/acme-expands"
    assert item.source.source_type == SourceType.COMPANY
    assert item.published_at is not None


def test_missing_summary_left_none():
    items, warnings = map_articles([article(summary=None)])
    assert items[0].summary is None
    assert warnings == []


def test_missing_publisher_left_none():
    items, warnings = map_articles([article(source=None)])
    assert items[0].source.publisher is None


def test_missing_date_leaves_published_at_none_with_warning():
    items, warnings = map_articles([article(datetime=None)])
    assert items[0].published_at is None
    assert any("no usable publication date" in w for w in warnings)


def test_zero_or_negative_datetime_treated_as_missing():
    items, warnings = map_articles([article(datetime=0)])
    assert items[0].published_at is None


def test_missing_url_skips_article():
    items, warnings = map_articles([article(url=None)])
    assert items == []
    assert any("missing or invalid URL" in w for w in warnings)


def test_invalid_url_skips_article():
    items, warnings = map_articles([article(url="not-a-url")])
    assert items == []
    assert any("missing or invalid URL" in w for w in warnings)


def test_dangerous_scheme_rejected():
    for scheme_url in [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html;base64,AAAA",
    ]:
        items, warnings = map_articles([article(url=scheme_url)])
        assert items == [], scheme_url
        assert any("missing or invalid URL" in w for w in warnings), scheme_url


def test_missing_headline_skips_article():
    items, warnings = map_articles([article(headline=None)])
    assert items == []
    assert any("no headline" in w for w in warnings)


def test_general_category_maps_to_news_source_type():
    items, _ = map_articles([article(category="general")])
    assert items[0].source.source_type == SourceType.NEWS


def test_no_invented_dates_urls_or_summaries():
    items, _ = map_articles([article(summary=None, datetime=None)])
    item = items[0]
    assert item.summary is None
    assert item.published_at is None
    # url is always present (article is skipped otherwise) -- never invented, always the source's own.
    assert item.source.url == article()["url"]


def test_multiple_articles_all_mapped():
    items, warnings = map_articles([article(url="https://a.com/1"), article(url="https://a.com/2")])
    assert len(items) == 2
    assert warnings == []
