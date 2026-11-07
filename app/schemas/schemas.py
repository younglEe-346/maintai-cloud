from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserRegister(BaseModel):
    org_name: str
    admin_email: EmailStr
    password: str
    plan: Optional[str] = "Standard"

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class MachineCreate(BaseModel):
    name: str

class MachineResponse(BaseModel):
    id: str
    name: str
    api_key: str
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class TelemetryItem(BaseModel):
    air_temp: float
    process_temp: float
    rotational_speed: float
    torque: float
    tool_wear: float

class TelemetryBatchIngest(BaseModel):
    machine_key: str
    metrics: List[TelemetryItem]

class AlertResponse(BaseModel):
    id: str
    machine_id: str
    risk_score: float
    status: str
    details: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True
