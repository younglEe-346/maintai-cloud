import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from app.worker.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.models import Telemetry, Alert

FEATURE_NAMES = [
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]"
]

def mock_predict(df_features: pd.DataFrame):
    # Rule-based fallback + model probability
    # If torque > 60 or tool_wear > 200 or temp diff < 8 -> high risk
    scores = []
    for idx, row in df_features.iterrows():
        air = row["Air temperature [K]"]
        proc = row["Process temperature [K]"]
        speed = row["Rotational speed [rpm]"]
        torque = row["Torque [Nm]"]
        wear = row["Tool wear [min]"]
        
        # High risk threshold logic
        if torque > 55 or wear > 200 or (proc - air) < 8.5 or speed > 2500:
            score = 0.95 + (np.random.rand() * 0.04) # 0.95 to 0.99
        else:
            score = 0.02 + (np.random.rand() * 0.05)
        scores.append(score)
    return scores

@celery_app.task
def process_telemetry_batch_async(machine_id: str, org_id: str, metrics: list):
    db = SessionLocal()
    try:
        # Save telemetry metrics
        telemetries = []
        rows = []
        for m in metrics:
            t = Telemetry(
                machine_id=machine_id,
                air_temp=m["air_temp"],
                process_temp=m["process_temp"],
                rotational_speed=m["rotational_speed"],
                torque=m["torque"],
                tool_wear=m["tool_wear"]
            )
            telemetries.append(t)
            rows.append([m["air_temp"], m["process_temp"], m["rotational_speed"], m["torque"], m["tool_wear"]])

        db.add_all(telemetries)
        db.commit()

        # Run Prediction
        df = pd.DataFrame(rows, columns=FEATURE_NAMES)
        risk_scores = mock_predict(df)

        # Create alert if risk_score > 0.85
        for score in risk_scores:
            if score > 0.85:
                alert = Alert(
                    org_id=org_id,
                    machine_id=machine_id,
                    risk_score=float(score),
                    status="OPEN",
                    details=f"High failure risk detected (Confidence: {score*100:.1f}%)"
                )
                db.add(alert)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error in async telemetry task: {e}")
    finally:
        db.close()
