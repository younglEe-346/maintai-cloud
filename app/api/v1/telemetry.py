from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.models.models import Machine
from app.schemas.schemas import TelemetryItem
from app.worker.tasks import process_telemetry_batch_async

router = APIRouter()

@router.post("/mesures")
def ingest_telemetry(
    metrics: List[TelemetryItem],
    x_api_key: str = Header(..., alias="x-api-key"),
    db: Session = Depends(get_db)
):
    machine = db.query(Machine).filter(Machine.api_key == x_api_key).first()
    if not machine:
        raise HTTPException(status_code=401, detail="Invalid Machine API Key")

    payload = [item.dict() for item in metrics]
    
    # Enqueue prediction job asynchronously in Celery
    process_telemetry_batch_async.delay(
        machine_id=machine.id,
        org_id=machine.org_id,
        metrics=payload
    )

    return {"status": "ingested", "processed_count": len(metrics)}
