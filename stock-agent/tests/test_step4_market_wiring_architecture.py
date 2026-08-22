"""Architectural guardrails for Step 4 (connect MarketDataService to the
ticker-analysis pipeline).

These aren't behavioral tests -- they assert structural properties the
Step 4 task explicitly required: the provider abstractions stay
separate, and the price-wiring code path goes through MarketDataService
rather than a second, ad-hoc HTTP client.
"""

import ast
from pathlib import Path

from app.data.base import FinancialDataProvider
from app.data.providers.indianapi import IndianAPIProvider
from app.market.base import MarketDataProvider

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_indianapi_provider_is_only_a_financial_data_provider():
    assert issubclass(IndianAPIProvider, FinancialDataProvider)
    assert not issubclass(IndianAPIProvider, MarketDataProvider)
    # IndianAPIProvider must not implement the MarketDataProvider contract
    # even informally -- it should have neither of MarketDataProvider's
    # abstract methods as anything but inherited-absent.
    assert not hasattr(IndianAPIProvider, "get_recent_prices")


def test_analyze_api_never_imports_httpx_directly():
    """`app/api/analyze.py` must reach FMP only through MarketDataService
    -> MarketDataProvider -> FMPMarketProvider -- never a direct HTTP
    client of its own."""
    imports = _imported_module_names(_REPO_ROOT / "app" / "api" / "analyze.py")
    assert not any(name == "httpx" or name.startswith("httpx.") for name in imports)


def test_application_service_never_imports_httpx_directly():
    imports = _imported_module_names(_REPO_ROOT / "app" / "application" / "service.py")
    assert not any(name == "httpx" or name.startswith("httpx.") for name in imports)


def test_pipeline_package_never_imports_httpx_directly():
    pipeline_dir = _REPO_ROOT / "app" / "pipeline"
    for path in pipeline_dir.glob("*.py"):
        imports = _imported_module_names(path)
        assert not any(name == "httpx" or name.startswith("httpx.") for name in imports), path


def test_analyze_api_reaches_fmp_only_through_market_data_service():
    """`app/api/analyze.py` may reference the market-data factory/service
    (the intended entry point), but must never import an FMP provider or
    client class directly -- that would be a second, ad-hoc integration
    bypassing MarketDataService."""
    imports = _imported_module_names(_REPO_ROOT / "app" / "api" / "analyze.py")
    assert "app.market.factory" in imports
    assert "app.market.service" in imports
    assert not any("providers.fmp" in name for name in imports)
