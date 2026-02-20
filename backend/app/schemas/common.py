from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(ORMModel):
    message: str


class HealthResponse(ORMModel):
    service: str
    status: str
    timestamp: datetime


class UUIDResponse(ORMModel):
    id: UUID

