from pydantic import BaseModel, Field


class AppConfigResponse(BaseModel):
    key: str
    value: str

    model_config = {"from_attributes": True}


class AppConfigUpdate(BaseModel):
    value: str = Field(min_length=0)
