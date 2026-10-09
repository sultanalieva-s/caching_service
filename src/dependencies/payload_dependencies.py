from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies.database_dependencies import get_session
from src.services.payload_service import PayloadService


def get_payload_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PayloadService:
    return PayloadService(session)