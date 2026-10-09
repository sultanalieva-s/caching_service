# tests/unit/test_payload_service.py
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from src.services.payload_service import PayloadNotFoundError, PayloadService


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(session: AsyncMock) -> PayloadService:
    svc = PayloadService(session)
    # Spy on the "external service" so tests can assert how often it is called.
    svc.transform = AsyncMock(side_effect=lambda strings: [s.upper() for s in strings])
    return svc


def cached_row(source: str, result: str) -> SimpleNamespace:
    return SimpleNamespace(source=source, result=result)


# --- pure functions ---------------------------------------------------------


def test_interleave_alternates_items():
    assert PayloadService.interleave(["a", "b"], ["x", "y"]) == ["a", "x", "b", "y"]


def test_interleave_rejects_length_mismatch():
    with pytest.raises(ValueError):
        PayloadService.interleave(["a"], ["x", "y"])


def test_compute_id_is_deterministic_and_order_sensitive():
    assert PayloadService._compute_id(["a"], ["b"]) == PayloadService._compute_id(["a"], ["b"])
    assert PayloadService._compute_id(["a"], ["b"]) != PayloadService._compute_id(["b"], ["a"])


def test_compute_id_distinguishes_joined_strings():
    assert PayloadService._compute_id(["a,b"], ["c"]) != PayloadService._compute_id(["a", "b"], ["c"])


# --- get_payload ------------------------------------------------------------


async def test_get_payload_returns_output(service, session):
    session.get.return_value = SimpleNamespace(output="A, B")

    assert await service.get_payload("some-id") == "A, B"


async def test_get_payload_raises_when_missing(service, session):
    session.get.return_value = None

    with pytest.raises(PayloadNotFoundError):
        await service.get_payload("missing")


# --- caching behaviour ------------------------------------------------------


async def test_transform_with_cache_only_transforms_misses(service, session):
    session.scalars.return_value = [cached_row("a", "A")]

    result = await service._transform_with_cache(["a", "b", "b"])

    assert result == {"a": "A", "b": "B"}
    # Single batched call, only for the uncached and deduplicated string.
    service.transform.assert_awaited_once_with(["b"])


async def test_transform_with_cache_skips_transformer_when_all_cached(service, session):
    session.scalars.return_value = [cached_row("a", "A"), cached_row("b", "B")]

    result = await service._transform_with_cache(["a", "b"])

    assert result == {"a": "A", "b": "B"}
    service.transform.assert_not_awaited()


async def test_create_payload_reuses_existing_payload(service, session):
    session.get.return_value = SimpleNamespace(output="whatever")

    payload_id = await service.create_payload(["a"], ["b"])

    assert payload_id == PayloadService._compute_id(["a"], ["b"])
    service.transform.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_create_payload_stores_interleaved_output(service, session):
    session.get.return_value = None
    session.scalars.return_value = []

    payload_id = await service.create_payload(["first", "second"], ["other", "another"])

    # The last execute() is the Payload insert; read the values it would write.
    stmt = session.execute.await_args_list[-1].args[0]
    params = stmt.compile(dialect=postgresql.dialect()).params
    assert params["id"] == payload_id
    assert params["output"] == "FIRST, OTHER, SECOND, ANOTHER"
    session.commit.assert_awaited_once()