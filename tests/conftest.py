import os
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from vendor_orchestrator import db as dbmod
from vendor_orchestrator.config import get_settings
from vendor_orchestrator.db import get_session, make_async_engine
from vendor_orchestrator.main import app
from vendor_orchestrator.models import Base
from vendor_orchestrator.vendors.mock_app import reset_mock_state

# Tests default to in-memory SQLite so pytest/CI run without Docker or Postgres.
# Point TEST_DATABASE_URL at Compose Postgres when you want that path.
DEFAULT_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB_URL)


async def _clear_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            await conn.execute(text("DELETE FROM vendor_calls"))
            await conn.execute(text("DELETE FROM cases"))
        else:
            await conn.execute(text("TRUNCATE TABLE vendor_calls, cases CASCADE"))


@pytest.fixture(autouse=True)
def _reset_mock_vendor_state() -> None:
    reset_mock_state()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    url = _test_database_url()
    engine = make_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    dbmod._engine = engine
    dbmod._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    dbmod._engine = None
    dbmod._session_factory = None
    get_settings.cache_clear()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await _clear_tables(engine)


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await _clear_tables(engine)
