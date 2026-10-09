import hashlib
import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.resource_access.models import Payload, TransformedString


class PayloadNotFoundError(Exception):
    pass


class PayloadService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_payload(self, list_1: list[str], list_2: list[str]) -> str:
        payload_id = self._compute_id(list_1, list_2)

        # Same input as before: skip all work, including transformer calls.
        if await self._session.get(Payload, payload_id):
            return payload_id

        transformed = await self._transform_with_cache([*list_1, *list_2])
        output = ", ".join(
            self.interleave(
                [transformed[s] for s in list_1],
                [transformed[s] for s in list_2],
            )
        )

        # Two identical requests can race past the check above; DO NOTHING makes
        # the loser a no-op since the output is deterministic.
        await self._session.execute(
            insert(Payload)
            .values(id=payload_id, output=output)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._session.commit()
        return payload_id

    async def get_payload(self, payload_id: str) -> str:
        payload = await self._session.get(Payload, payload_id)
        if payload is None:
            raise PayloadNotFoundError(payload_id)
        return payload.output

    async def _transform_with_cache(self, strings: list[str]) -> dict[str, str]:
        hashes = {s: self._hash(s) for s in set(strings)}

        rows = await self._session.scalars(
            select(TransformedString).where(
                TransformedString.source_hash.in_(hashes.values())
            )
        )
        result = {row.source: row.result for row in rows}

        missing = [s for s in hashes if s not in result]
        if missing:
            # One batched call for everything not cached yet.
            transformed = await self.transform(missing)
            await self._session.execute(
                insert(TransformedString)
                .values(
                    [
                        {"source_hash": hashes[s], "source": s, "result": r}
                        for s, r in zip(missing, transformed, strict=True)
                    ]
                )
                .on_conflict_do_nothing(index_elements=["source_hash"])
            )
            result.update(zip(missing, transformed, strict=True))

        return result

    async def transform(self, strings: list[str]) -> list[str]:
        """Stand-in for the external service."""
        return [s.upper() for s in strings]

    @staticmethod
    def interleave(list_1: list[str], list_2: list[str]) -> list[str]:
        # strict=True makes a length mismatch loud instead of silently truncating.
        return [item for pair in zip(list_1, list_2, strict=True) for item in pair]

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _compute_id(list_1: list[str], list_2: list[str]) -> str:
        # JSON encoding keeps ["a,b"] distinct from ["a", "b"], unlike naive joining.
        raw = json.dumps([list_1, list_2], separators=(",", ":"))
        return PayloadService._hash(raw)