import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Organization, Machine
from app.schemas.schemas import MachineCreate, MachineResponse
from app.api.v1.auth import get_current_org

router = APIRouter()

@router.post("", response_model=MachineResponse)
def create_machine(
    machine_in: MachineCreate,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db)
):
    api_key = f"maint_{secrets.token_urlsafe(16)}"
    machine = Machine(
        org_id=current_org.id,
        name=machine_in.name,
        api_key=api_key
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine

@router.get("", response_model=List[MachineResponse])
def list_machines(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db)
):
    return db.query(Machine).filter(Machine.org_id == current_org.id).all()
