from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Organization, Alert
from app.schemas.schemas import AlertResponse
from app.api.v1.auth import get_current_org

router = APIRouter()

@router.get("", response_model=List[AlertResponse])
def list_alerts(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db)
):
    return db.query(Alert).filter(Alert.org_id == current_org.id).order_by(Alert.created_at.desc()).all()
