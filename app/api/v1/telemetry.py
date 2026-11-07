"""Réception des mesures envoyées par les machines (authentification par clé d'API)."""
from typing import Any, List

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_org
from app.db.session import get_db
from app.models.models import Machine, Organization, QuarantinedMeasure, Telemetry
from app.services.validation import MAX_BATCH_SIZE, check_measure, utcnow
from app.worker.tasks import process_telemetry_batch_async

router = APIRouter()


def get_machine_by_key(x_api_key: str = Header(..., alias="x-api-key"), db: Session = Depends(get_db)) -> Machine:
    machine = db.query(Machine).filter(Machine.api_key == x_api_key).first()
    if not machine:
        raise HTTPException(status_code=401, detail="Clé d'API de machine invalide")
    return machine


@router.post("/mesures", status_code=status.HTTP_202_ACCEPTED)
def ingest_measures(
    batch: List[Any] = Body(..., description="Lot de mesures JSON (1 à 1000)"),
    machine: Machine = Depends(get_machine_by_key),
    db: Session = Depends(get_db),
):
    if not batch:
        raise HTTPException(status_code=422, detail="Le lot est vide")
    if len(batch) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=413, detail=f"Lot trop gros : {MAX_BATCH_SIZE} mesures maximum")

    now = utcnow()
    valid, rejected, duplicates, seen = [], [], [], set()

    # 1. Validation de chaque mesure ; les invalides vont en quarantaine avec leurs raisons
    for index, raw in enumerate(batch):
        measure, reasons = check_measure(raw)
        message_id = raw.get("message_id") if isinstance(raw, dict) else None
        if reasons:
            rejected.append({"index": index, "message_id": message_id, "reasons": reasons})
            db.add(QuarantinedMeasure(org_id=machine.org_id, machine_id=machine.id,
                                      message_id=str(message_id)[:128] if message_id is not None else None,
                                      payload=raw if isinstance(raw, dict) else {"valeur": raw},
                                      reasons=reasons, received_at=now))
        elif measure.message_id in seen:  # doublon à l'intérieur du même lot
            duplicates.append(measure.message_id)
        else:
            seen.add(measure.message_id)
            valid.append(measure)

    # 2. Enregistrement ; un message_id déjà reçu pour cette machine est ignoré (ON CONFLICT)
    accepted_ids = []
    if valid:
        rows = [{
            "machine_id": machine.id, "message_id": m.message_id,
            "timestamp": m.timestamp or now, "received_at": now,
            "air_temp": m.air_temp, "process_temp": m.process_temp,
            "rotational_speed": m.rotational_speed, "torque": m.torque, "tool_wear": m.tool_wear,
            "label_failure": m.label.failure if m.label else None,
            "label_modes": m.label.modes if m.label else None,
        } for m in valid]
        stmt = (insert(Telemetry).values(rows)
                .on_conflict_do_nothing(constraint="uq_telemetries_machine_message")
                .returning(Telemetry.id, Telemetry.message_id))
        inserted = {mid: tid for tid, mid in db.execute(stmt).all()}
        accepted_ids = [inserted[m.message_id] for m in valid if m.message_id in inserted]
        duplicates += [m.message_id for m in valid if m.message_id not in inserted]

    db.commit()

    # 3. Calcul du risque en arrière-plan (dans l'ordre d'arrivée)
    if accepted_ids:
        process_telemetry_batch_async.delay(machine_id=machine.id, telemetry_ids=accepted_ids)

    return {
        "accepted": len(accepted_ids),
        "duplicates": duplicates,
        "rejected": rejected,
    }


@router.get("/quarantaine")
def list_quarantine(limit: int = 100, current_org: Organization = Depends(get_current_org),
                    db: Session = Depends(get_db)):
    """Mesures rejetées de l'usine, avec les raisons du rejet (les plus récentes d'abord)."""
    rows = (db.query(QuarantinedMeasure).filter(QuarantinedMeasure.org_id == current_org.id)
            .order_by(QuarantinedMeasure.received_at.desc()).limit(min(limit, 1000)).all())
    return [{"id": q.id, "machine_id": q.machine_id, "message_id": q.message_id,
             "payload": q.payload, "reasons": q.reasons, "received_at": q.received_at} for q in rows]
