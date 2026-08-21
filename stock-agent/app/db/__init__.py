"""Persistence layer: async SQLAlchemy engine/session (`base.py`) and
ORM row models (`models.py`). Domain/API Pydantic models live under
`app/models/` instead — this package is intentionally the only place
that knows about tables, columns, and foreign keys.
"""
