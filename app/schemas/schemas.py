from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str


class MachineCreate(BaseModel):
    name: str


class MachineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    api_key: str
    status: str
    created_at: datetime


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    machine_id: str
    risk_score: float
    status: str  # OPEN, ACKNOWLEDGED (acquittée), CLOSED
    details: Optional[str] = None
    created_at: datetime
    peak_risk_score: Optional[float] = None
    last_risk_score: Optional[float] = None
    probable_mode: Optional[str] = None
    model_version: Optional[str] = None
    closed_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_name: Optional[str] = None
    ack_comment: Optional[str] = None
