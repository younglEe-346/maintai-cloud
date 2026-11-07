from datetime import datetime

from app.worker.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.models import Telemetry, Alert, Prediction, Machine, Organization
from app.ml.features import RAW_FEATURES
from app.ml.predictor import predict_risk
from app.services.hysteresis import Counters, HysteresisConfig, step


def alert_details(r: dict) -> str:
    mode = (r["failure_modes"] or {}).get("probable_mode") or "inconnu"
    explanation = (r["contributions"] or {}).get("explanation", "")
    return (f"Risque de panne {r['risk_score']:.1%} (seuil {r['threshold']:.1%}), "
            f"mode probable : {mode}. {explanation} ({r['model_version']})")


@celery_app.task
def process_telemetry_batch_async(machine_id: str, telemetry_ids: list):
    """Calcule le risque des mesures déjà enregistrées par l'API (dans l'ordre reçu)."""
    if not telemetry_ids:
        return
    db = SessionLocal()
    try:
        # Verrou sur la machine : deux lots de la même machine sont traités l'un après
        # l'autre, sinon les compteurs d'hystérésis pourraient être faussés.
        machine = db.query(Machine).filter(Machine.id == machine_id).with_for_update().one()
        org = db.get(Organization, machine.org_id)

        # 1. Relire les mesures, dans l'ordre d'arrivée
        by_id = {t.id: t for t in db.query(Telemetry).filter(Telemetry.id.in_(telemetry_ids))}
        telemetries = [by_id[i] for i in telemetry_ids if i in by_id]
        metrics = [{f: getattr(t, f) for f in RAW_FEATURES} for t in telemetries]
        if not telemetries:
            return

        # 2. Risque avec le seuil propre au ratio de coût de l'organisation
        results = predict_risk(metrics, cost_ratio=org.cost_ratio)
        high = results[0]["threshold"]
        cfg = HysteresisConfig(high=high, low=high * org.alert_close_factor,
                               open_k=org.alert_open_k, close_k=org.alert_close_k)

        # 3. Prédictions + hystérésis, mesure par mesure dans l'ordre reçu
        alert = (db.query(Alert)
                 .filter(Alert.machine_id == machine_id, Alert.status != "CLOSED")
                 .one_or_none())
        counters = Counters(machine.consecutive_high, machine.consecutive_low)
        for t, r in zip(telemetries, results):
            db.add(Prediction(telemetry_id=t.id, machine_id=machine_id, org_id=machine.org_id, **r))
            risk = r["risk_score"]
            action = step(counters, risk, cfg, alert_active=alert is not None)

            if action == "open":
                alert = Alert(
                    org_id=machine.org_id, machine_id=machine_id, status="OPEN",
                    risk_score=risk, peak_risk_score=risk, last_risk_score=risk,
                    probable_mode=(r["failure_modes"] or {}).get("probable_mode"),
                    model_version=r["model_version"], details=alert_details(r),
                )
                db.add(alert)
            elif alert is not None:
                alert.last_risk_score = risk
                if risk > (alert.peak_risk_score or 0):
                    # on garde le diagnostic du moment le plus grave
                    alert.peak_risk_score = risk
                    alert.probable_mode = (r["failure_modes"] or {}).get("probable_mode") or alert.probable_mode
                    alert.details = alert_details(r)
                if action == "close":
                    alert.status = "CLOSED"
                    alert.closed_at = datetime.utcnow()
                    alert = None

        machine.consecutive_high, machine.consecutive_low = counters.high, counters.low
        db.commit()
    except Exception:
        db.rollback()
        raise  # la tâche passe en échec dans Celery au lieu d'être ignorée en silence
    finally:
        db.close()
