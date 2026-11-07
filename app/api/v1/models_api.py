"""Modèle de l'usine : quel modèle est utilisé, historique, réentraînement (Pro)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_org, require_roles
from app.core.plans import plan_of
from app.db.session import get_db
from app.ml.selection import model_for_org
from app.models.models import Organization, OrgModel, User
from app.worker.tasks import retrain_org_model

router = APIRouter()


def job_out(j: OrgModel) -> dict:
    return {"id": j.id, "version": j.version, "name": j.name, "status": j.status,
            "message": j.message, "metrics": j.metrics, "created_at": j.created_at,
            "finished_at": j.finished_at}


@router.get("")
def models_overview(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    current = model_for_org(org, db)
    jobs = db.query(OrgModel).filter(OrgModel.org_id == org.id).order_by(OrgModel.version.desc()).all()
    return {"current_model": current["name"],
            "custom_model_allowed": plan_of(org)["custom_model"],
            "history": [job_out(j) for j in jobs]}


@router.post("/retrain", status_code=202)
def request_retraining(me: User = Depends(require_roles("owner", "admin")),
                       org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Lance le réentraînement en arrière-plan ; suivre le résultat avec GET /org/models."""
    if not plan_of(org)["custom_model"]:
        raise HTTPException(status_code=402, detail="Le réentraînement est réservé au plan Pro")
    running = db.query(OrgModel).filter(OrgModel.org_id == org.id, OrgModel.status == "training").first()
    if running is not None:
        raise HTTPException(status_code=409, detail="Un réentraînement est déjà en cours")
    version = (db.query(func.max(OrgModel.version)).filter(OrgModel.org_id == org.id).scalar() or 0) + 1
    job = OrgModel(org_id=org.id, version=version, name=f"org-{org.id[:8]}-v{version}",
                   status="training", requested_by_user_id=me.id)
    db.add(job)
    db.commit()
    retrain_org_model.delay(job.id)
    db.refresh(job)
    return job_out(job)
