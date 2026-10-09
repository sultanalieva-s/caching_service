# src/main.py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.resource_access.database import engine
from src.api.api_v1.endpoints import router as payload_router
from src.services.payload_service import PayloadNotFoundError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Close pooled connections cleanly on shutdown. Schema is owned by Alembic,
    # so there is nothing to create on startup.
    await engine.dispose()


app = FastAPI(
    title="Caching Service",
    version="0.1.0",
    description="Generates interleaved, transformed payloads and caches transformer results.",
    lifespan=lifespan,
)


@app.exception_handler(PayloadNotFoundError)
async def payload_not_found_handler(request: Request, exc: PayloadNotFoundError) -> JSONResponse:
    # Translating here keeps HTTP concerns out of the service layer.
    return JSONResponse(status_code=404, content={"detail": "Payload not found"})


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(payload_router, prefix="/payload", tags=["payload"])