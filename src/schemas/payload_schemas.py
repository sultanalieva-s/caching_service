from pydantic import BaseModel


class CreatePayloadRequest(BaseModel):
    list_1: list[str]
    list_2: list[str]

class CreatePayloadResponse(BaseModel):
    id: str

class GetPayloadResponse(BaseModel):
    output: str