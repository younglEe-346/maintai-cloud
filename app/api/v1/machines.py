"""Machines de l'usine et leurs clés d'API."""
import secrets
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_org, require_roles
from app.core.plans import plan_of
from app.core.security import hash_token
from app.db.session import get_db
from app.ml.features import RAW_FEATURES
from app.models.models import Machine, Organization, Prediction, Telemetry, User
from app.schemas.schemas import MachineCreate, MachineResponse, MachineWithKey

router = APIRouter()

KEY_WARNING = "Copiez cette clé maintenant : elle ne sera plus jamais affichée."


def new_api_key(machine: Machine) -> str:
    """Génère une clé (192 bits aléatoires) ; seule son empreinte est gardée."""
    key = f"maint_{secrets.token_urlsafe(24)}"
    machine.api_key_hash = hash_token(key)
    machine.api_key_prefix = key[:12]
    machine.api_key_created_at = datetime.utcnow()
    machine.api_key_revoked_at = None
    return key


def with_key(machine: Machine, key: str) -> dict:
    return {**MachineResponse.model_validate(machine).model_dump(), "api_key": key, "warning": KEY_WARNING}


@router.post("", response_model=MachineWithKey, status_code=201)
def create_machine(
    machine_in: MachineCreate,
    _: User = Depends(require_roles("owner", "admin")),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    plan = plan_of(current_org)
    active = db.query(Machine).filter(Machine.org_id == current_org.id, Machine.status == "ACTIVE").count()
    if active >= plan["max_machines"]:
        raise HTTPException(status_code=402, detail=(
            f"Limite du plan {plan['label']} atteinte : {plan['max_machines']} machines. "
            f"Archivez une machine ou passez au plan Pro."))
    machine = Machine(org_id=current_org.id, name=machine_in.name)
    key = new_api_key(machine)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return with_key(machine, key)


@router.get("", response_model=List[MachineResponse])
def list_machines(current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Liste des machines : la clé n'apparaît jamais, seulement son début (préfixe)."""
    return db.query(Machine).filter(Machine.org_id == current_org.id).order_by(Machine.created_at).all()


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


@router.delete("/{machine_id}", status_code=204)
def archive_machine(machine_id: str, _: User = Depends(require_roles("owner", "admin")),
                    current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Archive la machine : elle n'envoie plus de mesures et libère une place du plan.
    Son historique (mesures, alertes) est conservé."""
    machine = get_own_machine(machine_id, current_org, db)
    machine.status = "ARCHIVED"
    db.commit()


@router.post("/{machine_id}/api-key/revoke", response_model=MachineResponse)
def revoke_api_key(machine_id: str, _: User = Depends(require_roles("owner", "admin")),
                   current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Révoque la clé (ex. boîtier volé) : les mesures envoyées avec elle sont refusées (401)."""
    machine = get_own_machine(machine_id, current_org, db)
    if machine.api_key_revoked_at is None:
        machine.api_key_revoked_at = datetime.utcnow()
        db.commit()
    return machine


@router.post("/{machine_id}/api-key/rotate", response_model=MachineWithKey)
def rotate_api_key(machine_id: str, _: User = Depends(require_roles("owner", "admin")),
                   current_org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """Remplace la clé : l'ancienne cesse de fonctionner, la nouvelle est montrée une seule fois."""
    machine = get_own_machine(machine_id, current_org, db)
    if machine.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Machine archivée")
    key = new_api_key(machine)
    db.commit()
    db.refresh(machine)
    return with_key(machine, key)
