from pydantic import BaseModel, model_validator


class CreatePayloadRequest(BaseModel):
    list_1: list[str]
    list_2: list[str]

    @model_validator(mode="after")
    def lists_must_have_same_length(self) -> "CreatePayloadRequest":
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        return self

class CreatePayloadResponse(BaseModel):
    id: str

class GetPayloadResponse(BaseModel):
    output: str