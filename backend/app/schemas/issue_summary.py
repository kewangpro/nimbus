from pydantic import BaseModel
from uuid import UUID


class IssueSummary(BaseModel):
    issue_id: UUID
    summary: str
    next_steps: list[str]

    class Config:
        from_attributes = True
