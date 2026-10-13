import os

import httpx
import pytest_asyncio
from sqlalchemy import insert, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Tests may only connect to an explicitly named test database.
TEST_URL = make_url(os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kvitto_test:kvitto_test@localhost:55433/kvitto_test",
))
if not TEST_URL.database or not TEST_URL.database.endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must name a dedicated database ending in _test")
if TEST_URL.drivername != "postgresql+asyncpg":
    raise RuntimeError("Tests require PostgreSQL with asyncpg")

os.environ.update(
    DB_HOST=TEST_URL.host or "localhost",
    DB_PORT=str(TEST_URL.port or 5432),
    DB_NAME=TEST_URL.database,
    DB_USER=TEST_URL.username or "",
    DB_PASSWORD=TEST_URL.password or "",
)

from app.main import app
import app.main as main_module
from app.db.migrations import apply_migrations
from app.db.session import get_session
from app.models import Tariff

TARIFFS = [
    {"id": "basic", "title": "Basic", "price": 990000},
    {"id": "standard", "title": "Standard", "price": 1990000},
    {"id": "premium", "title": "Premium", "price": 2990000},
]


@pytest_asyncio.fixture
async def database():
    engine = create_async_engine(TEST_URL, poolclass=NullPool)
    try:
        await apply_migrations(engine)
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE payments, tariffs"))
            await connection.execute(insert(Tariff), TARIFFS)
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def sessions(database):
    return async_sessionmaker(database, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(database, sessions, monkeypatch):
    async def override_session():
        async with sessions() as session:
            yield session

    monkeypatch.setattr(main_module, "engine", database)
    app.dependency_overrides[get_session] = override_session
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client
    finally:
        app.dependency_overrides.clear()
