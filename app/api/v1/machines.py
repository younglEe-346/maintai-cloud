import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ml.features import RAW_FEATURES
from app.models.models import Organization, Machine, Telemetry, Prediction
from app.schemas.schemas import MachineCreate, MachineResponse
from app.core.deps import get_current_org, require_roles
from app.models.models import User

router = APIRouter()

@router.post("", response_model=MachineResponse)
def create_machine(
    machine_in: MachineCreate,
    _: User = Depends(require_roles("owner", "admin")),
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


def get_own_machine(machine_id: str, org: Organization, db: Session) -> Machine:
    """Une machine d'une autre usine répond 404 : on ne révèle même pas qu'elle existe."""
    machine = db.query(Machine).filter(Machine.id == machine_id, Machine.org_id == org.id).first()
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine introuvable")
    return machine


@router.get("/{machine_id}/mesures")
def list_measures(
    machine_id: str,
    limit: int = Query(200, ge=1, le=5000),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Dernières mesures de la machine avec leur prédiction (risque, mode, explication)."""
    get_own_machine(machine_id, current_org, db)
    rows = (db.query(Telemetry, Prediction)
            .outerjoin(Prediction, Prediction.telemetry_id == Telemetry.id)
            .filter(Telemetry.machine_id == machine_id)
            .order_by(Telemetry.timestamp.desc(), Telemetry.received_at.desc())
            .limit(limit).all())
    out = []
    for t, p in rows:
        item = {"id": t.id, "message_id": t.message_id, "timestamp": t.timestamp,
                **{f: getattr(t, f) for f in RAW_FEATURES},
                "label_failure": t.label_failure, "label_modes": t.label_modes, "prediction": None}
        if p is not None:
            item["prediction"] = {
                "risk_score": p.risk_score, "decision": p.decision, "threshold": p.threshold,
                "model_version": p.model_version,
                "probable_mode": (p.failure_modes or {}).get("probable_mode"),
                "explanation": (p.contributions or {}).get("explanation"),
                "contributions": (p.contributions or {}).get("contributions"),
            }
        out.append(item)
    return out
