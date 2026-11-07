"""Réentraînement du modèle d'une usine (plan Pro).

1. On récupère les mesures de l'usine qui ont un retour terrain (label).
2. On met 25 % de côté (jamais vus), on entraîne un CANDIDAT sur les 75 % restants.
3. On compare candidat et modèle actuel sur ces 25 %, avec le coût de l'usine.
4. Le candidat est PROMU seulement s'il coûte moins cher ; il est alors réentraîné
   sur 100 % des données et sauvegardé dans le dossier de l'usine.
"""
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from app.config import ORG_MODELS_DIR
from app.ml.cost import confusion_at
from app.ml.features import RAW_FEATURES
from app.ml.predictor import threshold_info
from app.ml.selection import model_for_org
from app.ml.training import SEED, train_bundle
from app.models.models import Machine, Organization, OrgModel, Telemetry

MIN_LABELED = 500    # mesures étiquetées minimum
MIN_FAILURES = 10    # pannes minimum parmi elles
MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]


class NotEnoughData(Exception):
    pass


def labeled_data(db: Session, org_id: str) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    rows = (db.query(Telemetry)
            .join(Machine, Machine.id == Telemetry.machine_id)
            .filter(Machine.org_id == org_id, Telemetry.label_failure.isnot(None))
            .order_by(Telemetry.received_at, Telemetry.timestamp, Telemetry.message_id).all())
    X = pd.DataFrame([{f: getattr(t, f) for f in RAW_FEATURES} for t in rows], columns=RAW_FEATURES)
    y = np.array([int(t.label_failure) for t in rows], dtype=int)
    modes = pd.DataFrame([{m: int(m in (t.label_modes or [])) for m in MODES} for t in rows], columns=MODES)
    return X, y, modes


def evaluate(artifact: dict, X: pd.DataFrame, y: np.ndarray, threshold: float, cost_ratio: float) -> dict:
    proba = artifact["pipeline"].predict_proba(X[RAW_FEATURES])[:, 1]
    c = confusion_at(y, proba, threshold, cost_ratio)
    c["pr_auc"] = float(average_precision_score(y, proba)) if y.sum() else None
    return c


def run_retraining(db: Session, job: OrgModel) -> OrgModel:
    org = db.get(Organization, job.org_id)
    ratio = org.cost_ratio
    X, y, modes = labeled_data(db, org.id)
    if len(y) < MIN_LABELED or y.sum() < MIN_FAILURES:
        raise NotEnoughData(
            f"Pas assez de données étiquetées : {len(y)} mesures dont {int(y.sum())} pannes "
            f"(minimum {MIN_LABELED} mesures et {MIN_FAILURES} pannes). Envoyez le champ "
            f"\"label\" (retour terrain) avec vos mesures.")

    # 1. données mises de côté pour la comparaison
    idx = np.arange(len(y))
    idx_tr, idx_te = train_test_split(idx, test_size=0.25, stratify=y, random_state=SEED)

    # 2. candidat entraîné sur 75 %
    cand = train_bundle(X.iloc[idx_tr], y[idx_tr], modes.iloc[idx_tr], ratio)
    cand_eval = evaluate(cand, X.iloc[idx_te], y[idx_te], cand["threshold"], ratio)

    # 3. modèle actuel (commun ou ancien modèle de l'usine), avec le seuil de l'usine
    current = model_for_org(org, db)
    current_eval = evaluate(current, X.iloc[idx_te], y[idx_te],
                            threshold_info(current, ratio)["threshold"], ratio)

    promoted = cand_eval["cost"] < current_eval["cost"]
    job.metrics = {"cost_ratio": ratio, "labeled_rows": int(len(y)), "failures": int(y.sum()),
                   "holdout_rows": int(len(idx_te)), "candidate": cand_eval,
                   "current": {**current_eval, "model_version": current["name"]},
                   "promoted": promoted}

    if not promoted:
        job.status = "rejected"
        job.message = (f"Candidat non promu : coût {cand_eval['cost']:.0f} contre "
                       f"{current_eval['cost']:.0f} pour le modèle actuel ({current['name']}) "
                       f"sur {len(idx_te)} mesures mises de côté.")
        return job

    # 4. promotion : réentraîné sur 100 % des données de l'usine
    final = train_bundle(X, y, modes, ratio)
    final.update({"name": job.name, "version": job.version, "org_id": org.id,
                  "trained_at": datetime.utcnow().isoformat(timespec="seconds")})
    folder = Path(ORG_MODELS_DIR) / org.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"risk_model_v{job.version}.joblib"
    joblib.dump(final, path, compress=3)

    db.query(OrgModel).filter(OrgModel.org_id == org.id, OrgModel.status == "active") \
        .update({"status": "retired"})
    db.flush()
    job.status, job.path = "active", str(path)
    job.message = (f"Candidat promu : coût {cand_eval['cost']:.0f} contre "
                   f"{current_eval['cost']:.0f} pour {current['name']} "
                   f"sur {len(idx_te)} mesures mises de côté.")
    return job
