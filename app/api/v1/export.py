"""Export CSV des données de l'usine (plan Pro).

Le fichier est envoyé en flux (ligne par ligne) : on peut exporter des centaines de
milliers de mesures sans tout charger en mémoire.
"""
import csv
import io
from datetime import datetime
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_org, require_roles
from app.core.plans import plan_of
from app.db.session import get_db
from app.ml.features import RAW_FEATURES
from app.models.models import Alert, Machine, Organization, Prediction, Telemetry, User

router = APIRouter()

MEASURE_COLUMNS = (["machine", "message_id", "timestamp"] + RAW_FEATURES +
                   ["risk_score", "decision", "threshold", "model_version", "probable_mode",
                    "explanation", "label_failure", "label_modes"])
ALERT_COLUMNS = ["machine", "status", "created_at", "risk_score", "peak_risk_score", "probable_mode",
                 "model_version", "acknowledged_by", "acknowledged_at", "ack_comment", "closed_at", "details"]


def require_export(org: Organization = Depends(get_current_org),
                   _: User = Depends(require_roles("owner", "admin"))) -> Organization:
    if not plan_of(org)["export"]:
        raise HTTPException(status_code=402, detail="L'export est réservé au plan Pro")
    return org


def csv_stream(header: list, rows: Iterator[list]) -> Iterator[str]:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")  # ";" : s'ouvre directement dans Excel en français
    writer.writerow(header)
    yield "﻿" + buf.getvalue()  # BOM : Excel reconnaît l'UTF-8 (accents)
    for row in rows:
        buf.seek(0)
        buf.truncate()
        writer.writerow(row)
        yield buf.getvalue()


def as_csv(header: list, rows: Iterator[list], name: str) -> StreamingResponse:
    filename = f"maintai_{name}_{datetime.utcnow():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(csv_stream(header, rows), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/mesures.csv")
def export_measures(
    machine_id: Optional[str] = None,
    start: Optional[datetime] = Query(None, description="à partir de (ISO 8601)"),
    end: Optional[datetime] = Query(None, description="jusqu'à (ISO 8601)"),
    org: Organization = Depends(require_export),
    db: Session = Depends(get_db),
):
    q = (db.query(Telemetry, Prediction, Machine.name)
         .join(Machine, Machine.id == Telemetry.machine_id)
         .outerjoin(Prediction, Prediction.telemetry_id == Telemetry.id)
         .filter(Machine.org_id == org.id))   # isolation : seulement les machines de l'usine
    if machine_id:
        q = q.filter(Machine.id == machine_id)
    if start:
        q = q.filter(Telemetry.timestamp >= start)
    if end:
        q = q.filter(Telemetry.timestamp <= end)
    q = q.order_by(Telemetry.timestamp, Telemetry.received_at).yield_per(1000)

    def rows():
        for t, p, machine_name in q:
            pred = [p.risk_score, p.decision, p.threshold, p.model_version,
                    (p.failure_modes or {}).get("probable_mode"),
                    (p.contributions or {}).get("explanation")] if p else [None] * 6
            yield ([machine_name, t.message_id, t.timestamp.isoformat()] +
                   [getattr(t, f) for f in RAW_FEATURES] + pred +
                   [t.label_failure, " ".join(t.label_modes or [])])
    return as_csv(MEASURE_COLUMNS, rows(), "mesures")


@router.get("/alertes.csv")
def export_alerts(org: Organization = Depends(require_export), db: Session = Depends(get_db)):
    q = (db.query(Alert, Machine.name).join(Machine, Machine.id == Alert.machine_id)
         .filter(Alert.org_id == org.id).order_by(Alert.created_at).yield_per(1000))

    def rows():
        for a, machine_name in q:
            yield [machine_name, a.status, a.created_at.isoformat(), a.risk_score, a.peak_risk_score,
                   a.probable_mode, a.model_version, a.acknowledged_by_name,
                   a.acknowledged_at.isoformat() if a.acknowledged_at else None, a.ack_comment,
                   a.closed_at.isoformat() if a.closed_at else None, a.details]
    return as_csv(ALERT_COLUMNS, rows(), "alertes")
