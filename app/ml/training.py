"""Entraînement réutilisable : utilisé par ml/train.py (modèle commun, AI4I) et par le
réentraînement Pro (modèle d'une usine, sur ses propres mesures étiquetées).

Les deux suivent exactement la même méthode (partie 1 de docs/EXPLICATIONS.md) :
Random Forest équilibré, seuil de coût sur probabilités hors-échantillon, un
classifieur par mode de panne, machine de référence pour les contributions.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from app.ml.cost import best_f1_threshold, best_threshold
from app.ml.features import RAW_FEATURES, build_features

SEED = 42
MIN_LIFT = 5  # un mode est "prédictible" si sa PR-AUC dépasse 5 fois celle du hasard
MIN_MODE_POSITIVES = 5  # validation croisée en 5 blocs : au moins 5 exemples positifs


def candidates() -> dict:
    feats = FunctionTransformer(build_features)
    return {
        "logistic_regression": Pipeline([
            ("features", feats), ("scale", StandardScaler()),
            ("model", LogisticRegression(class_weight="balanced", max_iter=5000)),
        ]),
        "random_forest": Pipeline([
            ("features", feats),
            ("model", RandomForestClassifier(
                n_estimators=300, class_weight="balanced_subsample",
                n_jobs=-1, random_state=SEED)),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("features", feats),
            ("model", HistGradientBoostingClassifier(class_weight="balanced", random_state=SEED)),
        ]),
    }


def oof_proba(pipeline, X, y) -> np.ndarray:
    """Probabilités hors-échantillon : chaque ligne est prédite par un modèle
    qui ne l'a jamais vue (validation croisée stratifiée en 5 blocs)."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    return cross_val_predict(pipeline, X, y, cv=cv, method="predict_proba")[:, 1]


def train_bundle(X: pd.DataFrame, y: np.ndarray, modes: pd.DataFrame, cost_ratio: float,
                 algorithm: str = "random_forest") -> dict:
    """Entraîne tout ce dont le worker a besoin. Renvoie les éléments d'un modèle
    (sans nom ni version : c'est à l'appelant de les ajouter)."""
    X = X[RAW_FEATURES].reset_index(drop=True)
    y = np.asarray(y).astype(int)

    # risque de panne + seuil de coût sur probabilités hors-échantillon
    oof = oof_proba(candidates()[algorithm], X, y)
    thr = best_threshold(y, oof, cost_ratio)
    pipeline = candidates()[algorithm].fit(X, y)

    # modes de panne : un classifieur oui/non par mode
    mode_models, mode_thresholds, predictable, mode_report = {}, {}, [], {}
    for m in modes.columns:
        ym = modes[m].to_numpy().astype(int)
        n_pos = int(ym.sum())
        if n_pos < MIN_MODE_POSITIVES:
            mode_report[m] = {"count": n_pos, "predictable": False,
                              "reason": f"moins de {MIN_MODE_POSITIVES} exemples"}
            continue
        oof_m = oof_proba(candidates()[algorithm], X, ym)
        pr_auc, prevalence = float(average_precision_score(ym, oof_m)), float(ym.mean())
        ok = pr_auc >= MIN_LIFT * prevalence
        mode_models[m] = candidates()[algorithm].fit(X, ym)
        mode_thresholds[m] = best_f1_threshold(ym, oof_m)["threshold"]
        if ok:
            predictable.append(m)
        mode_report[m] = {"count": n_pos, "prevalence": prevalence, "pr_auc_oof": pr_auc, "predictable": ok}

    return {
        "algorithm": algorithm,
        "pipeline": pipeline,
        "raw_features": RAW_FEATURES,
        "cost_ratio": float(cost_ratio),
        "threshold": thr["threshold"],
        "oof_proba": oof.astype(np.float32),
        "oof_y": y.astype(np.int8),
        "mode_models": mode_models,
        "mode_thresholds": mode_thresholds,
        "predictable_modes": predictable,
        # machine de référence pour les contributions : médiane des cycles sans panne
        "reference": {f: float(v) for f, v in X[y == 0].median().items()},
        "metrics": {"oof_pr_auc": float(average_precision_score(y, oof)),
                    "deployed_threshold": thr, "modes": mode_report,
                    "rows": int(len(y)), "failures": int(y.sum())},
    }
