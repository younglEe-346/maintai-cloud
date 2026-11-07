from app.worker.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.models import Telemetry, Alert, Prediction
from app.ml.predictor import predict_risk


@celery_app.task
def process_telemetry_batch_async(machine_id: str, org_id: str, metrics: list):
    db = SessionLocal()
    try:
        # 1. Enregistrer les mesures
        telemetries = [
            Telemetry(
                machine_id=machine_id,
                air_temp=m["air_temp"],
                process_temp=m["process_temp"],
                rotational_speed=m["rotational_speed"],
                torque=m["torque"],
                tool_wear=m["tool_wear"],
            )
            for m in metrics
        ]
        db.add_all(telemetries)
        db.flush()  # attribue les id des mesures avant de créer les prédictions

        # 2. Calculer le risque avec le modèle versionné
        results = predict_risk(metrics)

        # 3. Enregistrer chaque prédiction avec la version du modèle
        for t, r in zip(telemetries, results):
            db.add(Prediction(telemetry_id=t.id, machine_id=machine_id, org_id=org_id, **r))
            # Alerte simple (l'hystérésis viendra à une étape suivante)
            if r["decision"]:
                mode = (r["failure_modes"] or {}).get("probable_mode") or "inconnu"
                db.add(Alert(
                    org_id=org_id,
                    machine_id=machine_id,
                    risk_score=r["risk_score"],
                    status="OPEN",
                    details=(f"Risque de panne {r['risk_score']:.1%} >= seuil {r['threshold']:.1%}, "
                             f"mode probable : {mode}. "
                             f"{(r['contributions'] or {}).get('explanation', '')} ({r['model_version']})"),
                ))
        db.commit()
    except Exception:
        db.rollback()
        raise  # la tâche passe en échec dans Celery au lieu d'être ignorée en silence
    finally:
        db.close()
