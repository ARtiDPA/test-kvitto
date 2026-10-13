from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import payments, tariffs, webhooks
from app.db.migrations import apply_migrations
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await apply_migrations(engine)
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="Kvitto Payments API", lifespan=lifespan)
app.include_router(tariffs.router)
app.include_router(payments.router)
app.include_router(webhooks.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
