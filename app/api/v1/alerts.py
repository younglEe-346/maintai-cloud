"""Alertes de l'usine : consultation et acquittement par un technicien."""
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_org, get_current_user
from app.db.session import get_db
from app.models.models import Alert, Organization, User
from app.schemas.schemas import AlertResponse

router = APIRouter()

ACTIVE = ("OPEN", "ACKNOWLEDGED")


class AcknowledgeIn(BaseModel):
    comment: str = Field(default="", max_length=2000)


def get_own_alert(alert_id: str, org: Organization, db: Session) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.org_id == org.id).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    return alert


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    status: Optional[Literal["OPEN", "ACKNOWLEDGED", "CLOSED", "active"]] = Query(
        None, description="active = ouvertes ou acquittées"),
    machine_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    q = db.query(Alert).filter(Alert.org_id == current_org.id)
    if status == "active":
        q = q.filter(Alert.status.in_(ACTIVE))
    elif status:
        q = q.filter(Alert.status == status)
    if machine_id:
        q = q.filter(Alert.machine_id == machine_id)
    return q.order_by(Alert.created_at.desc()).limit(limit).all()


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: str, current_org: Organization = Depends(get_current_org),
              db: Session = Depends(get_db)):
    return get_own_alert(alert_id, current_org, db)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    body: AcknowledgeIn,
    user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Le technicien indique qu'il a pris l'alerte en charge. Elle reste active
    (le risque est toujours là) et se fermera seule quand le risque redescendra."""
    alert = get_own_alert(alert_id, current_org, db)
    if alert.status == "CLOSED":
        raise HTTPException(status_code=409, detail="Alerte déjà fermée")
    if alert.status == "ACKNOWLEDGED":
        raise HTTPException(status_code=409,
                            detail=f"Alerte déjà acquittée par {alert.acknowledged_by_name}")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by_name = user.full_name  # le nom vient du compte connecté
    alert.acknowledged_by_user_id = user.id
    alert.ack_comment = body.comment.strip() or None
    db.commit()
    db.refresh(alert)
    return alert
