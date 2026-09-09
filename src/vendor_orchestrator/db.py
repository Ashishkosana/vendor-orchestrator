from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from vendor_orchestrator.config import Settings, get_settings
from vendor_orchestrator.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

SQLITE_MEMORY_URL = "sqlite+aiosqlite:///:memory:"


def database_url_is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _is_sqlite_memory(url: str) -> bool:
    normalized = url.split("?", 1)[0].rstrip("/")
    return (
        normalized in {"sqlite+aiosqlite://", "sqlite://"}
        or normalized.endswith(":memory:")
        or normalized.endswith("://")
    )


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def make_async_engine(url: str) -> AsyncEngine:
    """Create an engine for Postgres (Compose/app) or SQLite (tests/evals)."""
    if database_url_is_sqlite(url):
        engine = create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if _is_sqlite_memory(url) else NullPool,
        )
        _enable_sqlite_foreign_keys(engine)
        return engine
    return create_async_engine(url, pool_pre_ping=True)


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        _engine = make_async_engine(cfg.database_url)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ping_db() -> None:
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def wait_for_db(settings: Settings | None = None) -> None:
    import asyncio

    cfg = settings or get_settings()
    last_error: Exception | None = None
    for _ in range(cfg.db_connect_attempts):
        try:
            await ping_db()
            return
        except Exception as exc:  # noqa: BLE001 — startup retry is intentional
            last_error = exc
            await asyncio.sleep(cfg.db_connect_delay_seconds)
    raise RuntimeError("Database was not reachable at startup") from last_error


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
