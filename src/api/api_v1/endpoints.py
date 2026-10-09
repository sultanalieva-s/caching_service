from typing import Annotated

from fastapi import APIRouter, Depends

from src.dependencies.payload_dependencies import get_payload_service
from src.schemas.payload_schemas import CreatePayloadResponse, CreatePayloadRequest, GetPayloadResponse
from src.services.payload_service import PayloadService

router = APIRouter()

@router.post("", description="Create payload", response_model=CreatePayloadResponse)
async def create_payload(
    payload_req: CreatePayloadRequest,
    service: Annotated[PayloadService, Depends(get_payload_service)],
):
    payload_id = await service.create_payload(payload_req.list_1, payload_req.list_2)
    return CreatePayloadResponse(id=payload_id)

@router.get("/{payload_id}", description="Get payload", response_model=GetPayloadResponse)
async def get_payload(
    payload_id: str,
    service: Annotated[PayloadService, Depends(get_payload_service)],
):
    output = await service.get_payload(payload_id)
    return GetPayloadResponse(output=output)