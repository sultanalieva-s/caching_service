from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.dependencies.payload_dependencies import get_payload_service  # fix path if you renamed it
from src.main import app


@pytest.fixture
def service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
async def client(service: AsyncMock) -> AsyncIterator[AsyncClient]:
    # Replace the real service (and, transitively, the DB session) with the mock.
    app.dependency_overrides[get_payload_service] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    # Overrides are global state on the app; always clean up.
    app.dependency_overrides.clear()