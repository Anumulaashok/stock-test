"""Cheap validation of the Screener session cookie.

Validation is one small search request — never a historical import. The
cookie value is never returned to a caller and never logged; only the
resulting status is.
"""

import logging
from datetime import datetime, timezone

from pydantic import BaseModel

from app.data.providers.screener_client import ScreenerClient, ScreenerImportError
from app.sources.provenance import SourceStatus

logger = logging.getLogger(__name__)

# A term that reliably matches something on Screener, so a valid cookie
# is never mistaken for an invalid one because of an empty result.
_PROBE_QUERY = "reliance"


class ScreenerCookieHealth(BaseModel):
    configured: bool
    source: str | None = None
    status: SourceStatus = SourceStatus.NOT_CONFIGURED
    last_validated_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    detail: str | None = None


async def validate_cookie(client: ScreenerClient, *, source: str | None) -> ScreenerCookieHealth:
    """Never raises — an unvalidatable cookie is a status, not an error."""
    now = datetime.now(timezone.utc).isoformat()

    if not client.has_cookie:
        return ScreenerCookieHealth(
            configured=False,
            source=None,
            status=SourceStatus.NOT_CONFIGURED,
            detail="No Screener session cookie is configured.",
        )

    try:
        await client.search_companies(_PROBE_QUERY)
    except ScreenerImportError as exc:
        status = exc.status
        # An auth rejection is the cookie's own problem; everything else
        # is Screener's, and must not be reported as an expired cookie.
        if status == SourceStatus.AUTH_EXPIRED:
            detail = "Screener rejected the session cookie. Sign in again and paste a fresh cookie."
        elif status == SourceStatus.RATE_LIMITED:
            detail = "Screener rate-limited the validation request; the cookie may still be valid."
        elif status == SourceStatus.UNREACHABLE:
            detail = "Screener could not be reached; the cookie could not be validated."
        else:
            detail = "Screener returned an unexpected response; the cookie could not be validated."
        logger.info("screener_cookie_validation status=%s", status.value)
        return ScreenerCookieHealth(
            configured=True,
            source=source,
            status=status,
            last_validated_at=now,
            last_error_at=now,
            detail=detail,
        )

    logger.info("screener_cookie_validation status=%s", SourceStatus.SUCCESS.value)
    return ScreenerCookieHealth(
        configured=True,
        source=source,
        status=SourceStatus.SUCCESS,
        last_validated_at=now,
        last_success_at=now,
    )
