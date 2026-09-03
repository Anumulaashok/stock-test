"""HTTP client for Screener.in's (unofficial) APIs — used only for a
one-time historical bulk-import backfill and company-id lookup (see
`app.data.screener_import_service`), never as a live `MarketDataProvider`/
`FinancialDataProvider`. Screener has no documented public API; this
hits the same endpoints the website's own UI calls:

    GET /api/company/{company_id}/chart/?q=Price-DMA50-DMA200-Volume&days={days}&consolidated={true|false}
    GET /api/company/search/?q={query}&v=5&fts=1

`company_id` is Screener's own opaque numeric id (visible in a
company's URL/API response, e.g. `/api/company/1298/chart/` for
HDFCBANK). The search endpoint resolves a company name/ticker to that
id (and to a canonical `/company/{TICKER}/...` URL, which is where the
ticker itself comes from — see `app.data.mappers.screener.map_screener_company_list`).

The chart endpoint works unauthenticated; the search endpoint, in
practice, needs a logged-in Screener session — set `SCREENER_SESSION_COOKIE`
(this app's own `.env`, never committed) to the `sessionid` cookie value
from a real browser session. The cookie value is only ever placed in an
outbound request header here, never logged.
"""

import asyncio
import logging

import httpx

from app.sources.provenance import SourceStatus

logger = logging.getLogger(__name__)

# Transient failures are worth one or two more attempts; an auth failure
# never is -- retrying an expired cookie only delays the fallback.
DEFAULT_MAX_RETRIES = 2
_BACKOFF_BASE_SECONDS = 0.5
# A Retry-After far in the future is not worth blocking a request on.
_MAX_HONOURED_RETRY_AFTER = 5.0


class ScreenerMappingNotFoundError(Exception):
    """Raised when `screener_company_id` is omitted and no stored
    mapping exists for the ticker yet — a client-input problem (missing
    prerequisite data), not an upstream Screener failure, so callers
    should map this to 400, not 502."""


class ScreenerImportError(Exception):
    """Raised for any Screener fetch failure — network, auth, or an
    unexpected response shape. Distinct from `app.data.exceptions.ProviderError`
    since this client is not a `FinancialDataProvider`/`MarketDataProvider`
    and is never called from the core analysis pipeline.

    Carries a `status` so the source manager can distinguish an expired
    cookie (fall back, don't retry) from a timeout (retry, then fall
    back) without parsing the message.
    """

    def __init__(self, message: str, status: SourceStatus = SourceStatus.ERROR) -> None:
        super().__init__(message)
        self.status = status


class ScreenerClient:
    def __init__(
        self,
        base_url: str = "https://www.screener.in",
        session_cookie: str | None = None,
        timeout_seconds: float = 20.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session_cookie = session_cookie
        self._timeout = httpx.Timeout(timeout_seconds)
        self._max_retries = max(0, max_retries)

    @property
    def has_cookie(self) -> bool:
        return bool(self._session_cookie)

    def _headers(self, *, xhr: bool = False) -> dict:
        headers: dict[str, str] = {}
        if self._session_cookie:
            headers["Cookie"] = f"sessionid={self._session_cookie}"
        if xhr:
            headers["X-Requested-With"] = "XMLHttpRequest"
        return headers

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return min(float(raw), _MAX_HONOURED_RETRY_AFTER)
        except ValueError:
            # Retry-After may also be an HTTP-date; not worth parsing here.
            return None

    def _classify(self, response: httpx.Response, path: str) -> ScreenerImportError | None:
        """Map a non-200 to an explicit status. The cookie value is never
        included in the message."""
        code = response.status_code
        if code == 200:
            return None
        if code in (401, 403):
            return ScreenerImportError(
                f"Screener rejected the session cookie ({code}) for {path}",
                SourceStatus.AUTH_EXPIRED,
            )
        if code == 429:
            return ScreenerImportError(
                f"Screener rate-limited the request (429) for {path}",
                SourceStatus.RATE_LIMITED,
            )
        if code >= 500:
            return ScreenerImportError(
                f"Screener is unavailable ({code}) for {path}", SourceStatus.UNREACHABLE
            )
        return ScreenerImportError(
            f"Screener returned status {code} for {path}", SourceStatus.INVALID
        )

    async def _get_json(self, path: str, params: dict, *, xhr: bool = False) -> object:
        url = f"{self._base_url}{path}"
        last_error: ScreenerImportError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, params=params, headers=self._headers(xhr=xhr))
            except httpx.TimeoutException as exc:
                last_error = ScreenerImportError(
                    f"Screener request timed out: {exc}", SourceStatus.UNREACHABLE
                )
            except httpx.RequestError as exc:
                logger.warning("screener_request_failed path=%s attempt=%d", path, attempt + 1)
                last_error = ScreenerImportError(
                    f"Screener request failed: {exc}", SourceStatus.UNREACHABLE
                )
            else:
                error = self._classify(response, path)
                if error is None:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ScreenerImportError(
                            "Screener returned malformed JSON", SourceStatus.INVALID
                        ) from exc

                # An expired cookie will not fix itself on the next attempt.
                if error.status in (SourceStatus.AUTH_EXPIRED, SourceStatus.INVALID):
                    logger.warning(
                        "screener_request_rejected path=%s status=%s", path, error.status.value
                    )
                    raise error

                last_error = error
                if error.status == SourceStatus.RATE_LIMITED:
                    delay = self._retry_after_seconds(response)
                    if delay is not None and attempt < self._max_retries:
                        await asyncio.sleep(delay)
                        continue

            if attempt < self._max_retries:
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (attempt + 1))

        raise last_error or ScreenerImportError("Screener request failed", SourceStatus.ERROR)

    async def get_chart(self, company_id: int, days: int = 365, consolidated: bool = True) -> dict:
        data = await self._get_json(
            f"/api/company/{company_id}/chart/",
            {"q": "Price-DMA50-DMA200-Volume", "days": days, "consolidated": "true" if consolidated else "false"},
        )
        if not isinstance(data, dict):
            raise ScreenerImportError(
                "Screener response was not a JSON object", SourceStatus.INVALID
            )
        return data

    async def search_companies(self, query: str) -> list:
        """`GET /api/company/search/?q={query}&v=5&fts=1` -- returns a
        plain list of `{id, name, url}` objects (plus Screener's own
        "Search everywhere: ..." sentinel row with `id: null`, which
        `map_screener_company_list` already knows to skip). Needs an
        authenticated session (`SCREENER_SESSION_COOKIE`) in practice."""
        data = await self._get_json(
            "/api/company/search/", {"q": query, "v": 5, "fts": 1}, xhr=True
        )
        if not isinstance(data, list):
            raise ScreenerImportError(
                "Screener search response was not a JSON array", SourceStatus.INVALID
            )
        return data
