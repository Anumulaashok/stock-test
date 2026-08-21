"""SQLAlchemy ORM models — persistence only.

Pydantic domain/API models live under `app/models/` as everywhere else
in this project; these row models are kept separate so persistence
schema changes never leak into API contracts (in particular,
`UserRow.password_hash` must never be serialized directly into a
response — API layers always map to `app.models.user.UserPublic`).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    portfolios: Mapped[list["PortfolioRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    watchlist_items: Mapped[list["WatchlistItemRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class PortfolioRow(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="My Portfolio")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["UserRow"] = relationship(back_populates="portfolios")
    holdings: Mapped[list["HoldingRow"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class HoldingRow(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "ticker", name="uq_holding_portfolio_ticker"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    portfolio: Mapped["PortfolioRow"] = relationship(back_populates="holdings")


class WatchlistItemRow(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user: Mapped["UserRow"] = relationship(back_populates="watchlist_items")


class RevokedTokenRow(Base):
    """Enables real logout semantics for otherwise-stateless JWTs: the
    token's `jti` is recorded here until its natural expiry."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
