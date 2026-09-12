"""SQLAlchemy declarative base shared by every ORM model. Alembic's `env.py` imports this metadata."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
