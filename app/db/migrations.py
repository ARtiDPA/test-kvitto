from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _upgrade(connection: Connection) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def apply_migrations(engine: AsyncEngine) -> None:
    """Apply migrations using the application's async engine and one transaction."""
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade)
