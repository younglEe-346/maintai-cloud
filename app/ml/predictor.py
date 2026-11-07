"""Utilisation d'un modèle par le worker et l'API (chargé une seule fois par processus)."""
import os
import pandas as pd

from app.ml.cost import best_threshold
from app.ml.explain import describe, shapley_contributions
from app.ml.features import RAW_FEATURES
from app.ml.registry import load_artifact

_artifact: dict | None = None


def get_artifact() -> dict:
    global _artifact
    if _artifact is None:
        version = os.getenv("MODEL_VERSION")
        _artifact = load_artifact(int(version) if version else None)
    return _artifact


_threshold_cache: dict = {}


def threshold_info(a: dict, cost_ratio: float) -> dict:
    """Seuil optimal pour un ratio de coût, recalculé à partir des probabilités
    hors-échantillon sauvegardées avec le modèle (pas de réentraînement).
    Renvoie aussi ce que ce seuil aurait donné sur ces données (rappel, fausses alertes)."""
    key = (a["name"], float(cost_ratio))
    if key not in _threshold_cache:
        info = best_threshold(a["oof_y"], a["oof_proba"], float(cost_ratio))
        info["evaluated_on"] = int(len(a["oof_y"]))
        _threshold_cache[key] = info
    return _threshold_cache[key]


def threshold_for_ratio(cost_ratio: float, a: dict | None = None) -> float:
    return threshold_info(a or get_artifact(), cost_ratio)["threshold"]


def predict_risk(rows: list[dict], cost_ratio: float | None = None, artifact: dict | None = None) -> list[dict]:
    a = artifact or get_artifact()
    threshold = a["threshold"] if cost_ratio is None else threshold_for_ratio(float(cost_ratio), a)
    X = pd.DataFrame(rows)[RAW_FEATURES]
    proba = a["pipeline"].predict_proba(X)[:, 1]
    modes = predict_modes(a, X)
    phi, base = (None, None)
    if "reference" in a:  # les modèles v1 et v2 n'ont pas de référence
        phi, base = shapley_contributions(lambda d: a["pipeline"].predict_proba(d)[:, 1], X, a["reference"])
    results = []
    for i, p in enumerate(proba):
        decision = bool(p >= threshold)
        failure_modes = None
        if modes is not None:
            probs = {m: float(modes[m][i]) for m in modes}
            failure_modes = {
                "probabilities": probs,
                # modes dont la probabilité dépasse leur propre seuil (plusieurs possibles)
                "flagged": [m for m in probs if probs[m] >= a["mode_thresholds"][m]],
                # le mode probable n'a de sens que si on alerte
                "probable_mode": max(probs, key=probs.get) if decision and probs else None,
            }
        contributions = None
        if phi is not None:
            values = {f: float(X.iloc[i][f]) for f in RAW_FEATURES}
            contrib = {f: float(c) for f, c in zip(RAW_FEATURES, phi[i])}
            contributions = {
                "base_risk": base,          # risque d'une machine "normale"
                "values": values,           # mesures reçues
                "reference": a["reference"],
                "contributions": contrib,   # base_risk + somme = risk_score
                "explanation": describe(values, contrib, a["reference"]),
            }
        results.append({
            "risk_score": float(p),
            "decision": decision,
            "threshold": float(threshold),
            "model_version": a["name"],
            "failure_modes": failure_modes,
            "contributions": contributions,
        })
    return results


def predict_modes(a: dict, X: pd.DataFrame) -> dict | None:
    """Probabilité de chaque mode prédictible (RNF exclu : pannes aléatoires).
    Renvoie None pour un ancien modèle sans modes (v1)."""
    if "mode_models" not in a:
        return None
    return {m: a["mode_models"][m].predict_proba(X)[:, 1] for m in a["predictable_modes"]}
