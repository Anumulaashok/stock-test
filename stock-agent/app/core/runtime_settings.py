"""Tiny runtime-editable settings store, backed by `AppSettingRow`.

Exists for exactly one setting: the Screener.in session cookie. Every
other setting in this app is an env var (`app.core.config.Settings`)
that requires a restart to change -- fine for infrastructure config,
but the cookie is a session credential that expires/rotates and the
user needs to update from the running app's own UI, without redeploying.
A DB row here (when present) takes precedence over the matching env var.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow

logger = logging.getLogger(__name__)

SCREENER_SESSION_COOKIE_KEY = "screener_session_cookie"


async def get_runtime_setting(db: AsyncSession, key: str) -> str | None:
    row = await db.get(AppSettingRow, key)
    return row.value if row is not None else None


async def set_runtime_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AppSettingRow, key)
    if row is None:
        db.add(AppSettingRow(key=key, value=value))
    else:
        row.value = value
    await db.commit()
    logger.info("runtime_setting_updated key=%s", key)


async def clear_runtime_setting(db: AsyncSession, key: str) -> None:
    row = await db.get(AppSettingRow, key)
    if row is not None:
        await db.delete(row)
        await db.commit()
        logger.info("runtime_setting_cleared key=%s", key)


async def resolve_screener_session_cookie(db: AsyncSession, env_value: str | None) -> str | None:
    """DB override wins when set; otherwise falls back to the env var
    (`SCREENER_SESSION_COOKIE`)."""
    stored = await get_runtime_setting(db, SCREENER_SESSION_COOKIE_KEY)
    return stored if stored else env_value
