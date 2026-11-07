"""Super-administrateur (équipe MaintAI) : suivi des usines et des workers.

Il voit des CHIFFRES (nombre de machines, de mesures, d'alertes), pas les mesures
elles-mêmes : les données des usines restent privées.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.organization import apply_plan
from app.core.deps import require_superadmin
from app.core.plans import plan_of
from app.db.session import get_db
from app.ml.selection import model_for_org
from app.models.models import Alert, Machine, Organization, Telemetry, User
from app.services.usage import _redis, measures_today
from app.worker.celery_app import celery_app

router = APIRouter()


class PlanIn(BaseModel):
    plan: Literal["FREE", "PRO"]


@router.get("/organizations")
def list_organizations(_: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    def count_by_org(query):
        return dict(query.all())

    members = count_by_org(db.query(User.org_id, func.count()).filter(User.is_active.is_(True))
                           .group_by(User.org_id))
    machines = count_by_org(db.query(Machine.org_id, func.count()).filter(Machine.status == "ACTIVE")
                            .group_by(Machine.org_id))
    active_alerts = count_by_org(db.query(Alert.org_id, func.count())
                                 .filter(Alert.status != "CLOSED").group_by(Alert.org_id))
    last_measure = count_by_org(db.query(Machine.org_id, func.max(Telemetry.received_at))
                                .join(Telemetry, Telemetry.machine_id == Machine.id).group_by(Machine.org_id))
    out = []
    for org in db.query(Organization).order_by(Organization.created_at).all():
        out.append({
            "id": org.id, "name": org.name, "plan": org.plan, "created_at": org.created_at,
            "members": members.get(org.id, 0),
            "machines": machines.get(org.id, 0), "max_machines": plan_of(org)["max_machines"],
            "measures_today": measures_today(org.id),
            "max_measures_per_day": plan_of(org)["max_measures_per_day"],
            "active_alerts": active_alerts.get(org.id, 0),
            "last_measure_at": last_measure.get(org.id),
            "model": model_for_org(org, db)["name"],
        })
    return out


@router.put("/organizations/{org_id}/plan")
def set_plan(org_id: str, body: PlanIn, _: User = Depends(require_superadmin), db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Usine introuvable")
    apply_plan(org, body.plan, db)
    db.commit()
    return {"id": org.id, "name": org.name, "plan": org.plan}


@router.get("/workers")
def workers(_: User = Depends(require_superadmin)):
    """État des workers Celery : qui répond, combien de tâches en cours, file d'attente."""
    inspect = celery_app.control.inspect(timeout=1.0)
    ping = inspect.ping() or {}
    active = inspect.active() or {}
    stats = inspect.stats() or {}
    try:
        queued = int(_redis().llen("celery"))  # tâches en attente dans la file Redis
    except Exception:
        queued = None
    return {
        "workers": [{"name": name, "online": True,
                     "active_tasks": len(active.get(name, [])),
                     "running": [t.get("name") for t in active.get(name, [])],
                     "processes": len((stats.get(name, {}).get("pool") or {}).get("processes", [])),
                     "tasks_done": stats.get(name, {}).get("total", {})}
                    for name in sorted(ping)],
        "queued_tasks": queued,
    }
