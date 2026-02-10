from pydantic import BaseModel
from uuid import UUID


class LabelBase(BaseModel):
    name: str


class Label(LabelBase):
    id: UUID

    class Config:
        from_attributes = True
