import pytest

from app.data.base import FinancialDataProvider
from app.data.exceptions import ProviderError
from app.data.models import (
    CompanyIdentifier,
    FinancialDataErrorCode,
    FinancialDataMetadata,
    FinancialDataResult,
)
from app.data.service import FinancialDataService
from app.models.financial_statements import CompanyFinancials


class FakeProvider(FinancialDataProvider):
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.calls = []

    async def get_company_financials(self, identifier: CompanyIdentifier) -> FinancialDataResult:
        self.calls.append(identifier)
        if self._raises:
            raise self._raises
        return self._result


def _success_result(ticker="ACME"):
    return FinancialDataResult(
        company_financials=CompanyFinancials(company_name=ticker, ticker=ticker),
        metadata=FinancialDataMetadata(
            provider="financial_modeling_prep", source_identifier=ticker, retrieved_at="2026-01-01T00:00:00Z"
        ),
        warnings=[],
    )


@pytest.mark.asyncio
async def test_successful_retrieval():
    provider = FakeProvider(result=_success_result())
    service = FinancialDataService(provider)

    result = await service.get_company_financials(CompanyIdentifier(ticker="acme"))

    assert result.status == "success"
    assert result.data.company_financials.ticker == "ACME"
    assert provider.calls[0].ticker == "ACME"  # normalized to uppercase


@pytest.mark.asyncio
async def test_empty_ticker_is_rejected_without_calling_provider():
    provider = FakeProvider()
    service = FinancialDataService(provider)

    result = await service.get_company_financials(CompanyIdentifier(ticker="  "))

    assert result.status == "error"
    assert result.error.code is FinancialDataErrorCode.MISSING_REQUIRED_DATA
    assert provider.calls == []


@pytest.mark.asyncio
async def test_company_not_found_maps_to_structured_error():
    provider = FakeProvider(raises=ProviderError(FinancialDataErrorCode.COMPANY_NOT_FOUND, "not found"))
    service = FinancialDataService(provider)

    result = await service.get_company_financials(CompanyIdentifier(ticker="NOPE"))

    assert result.status == "error"
    assert result.error.code is FinancialDataErrorCode.COMPANY_NOT_FOUND
    assert result.data is None


@pytest.mark.asyncio
async def test_provider_unavailable_maps_to_structured_error():
    provider = FakeProvider(raises=ProviderError(FinancialDataErrorCode.PROVIDER_UNAVAILABLE, "down"))
    service = FinancialDataService(provider)

    result = await service.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert result.status == "error"
    assert result.error.code is FinancialDataErrorCode.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_invalid_provider_data_maps_to_structured_error():
    provider = FakeProvider(raises=ProviderError(FinancialDataErrorCode.SCHEMA_MISMATCH, "bad schema"))
    service = FinancialDataService(provider)

    result = await service.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert result.status == "error"
    assert result.error.code is FinancialDataErrorCode.SCHEMA_MISMATCH


@pytest.mark.asyncio
async def test_warnings_propagate_from_provider_result():
    result_with_warnings = _success_result()
    result_with_warnings.warnings.append("duplicate income statement record for FY2023")
    provider = FakeProvider(result=result_with_warnings)
    service = FinancialDataService(provider)

    result = await service.get_company_financials(CompanyIdentifier(ticker="ACME"))

    assert result.data.warnings == ["duplicate income statement record for FY2023"]
