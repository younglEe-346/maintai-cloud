"""Coût des erreurs et seuil de décision optimal.

Règle de décision : on alerte si probabilité >= seuil.
Coût = ratio x (pannes manquées) + 1 x (fausses alertes).
Par défaut une panne manquée coûte 50 fois une fausse alerte.
"""
import numpy as np

DEFAULT_COST_RATIO = 50.0
NEVER_ALERT = 1.01  # seuil au-dessus de toute probabilité : on n'alerte jamais


def confusion_at(y, proba, threshold, cost_ratio=DEFAULT_COST_RATIO) -> dict:
    y = np.asarray(y).astype(int)
    alert = np.asarray(proba, dtype=float) >= threshold
    tp = int(((y == 1) & alert).sum())
    fn = int(((y == 1) & ~alert).sum())
    fp = int(((y == 0) & alert).sum())
    tn = int(((y == 0) & ~alert).sum())
    return {
        "threshold": float(threshold),
        "cost_ratio": float(cost_ratio),
        "cost": float(cost_ratio * fn + fp),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
    }


def best_threshold(y, proba, cost_ratio=DEFAULT_COST_RATIO) -> dict:
    """Teste tous les seuils utiles et garde celui qui coûte le moins.

    On trie les probabilités de la plus haute à la plus basse : alerter sur les
    k premières revient à placer le seuil juste en dessous de la k-ième.
    """
    y = np.asarray(y).astype(int)
    p = np.asarray(proba, dtype=float)
    order = np.argsort(-p, kind="mergesort")
    p_sorted, y_sorted = p[order], y[order]

    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    # on ne garde que la fin de chaque groupe de probabilités égales
    last = np.r_[p_sorted[1:] != p_sorted[:-1], True]
    tp, fp, p_low = tp[last], fp[last], p_sorted[last]
    # seuil placé au milieu entre la plus petite proba alertée et la suivante
    p_next = np.r_[p_low[1:], 0.0]
    thresholds = np.r_[NEVER_ALERT, (p_low + p_next) / 2]
    n_pos = int(y.sum())
    costs = np.r_[cost_ratio * n_pos, cost_ratio * (n_pos - tp) + fp]

    best = int(np.argmin(costs))  # à coût égal : le seuil le plus haut (moins d'alertes)
    return confusion_at(y, p, thresholds[best], cost_ratio)


def best_f1_threshold(y, proba) -> dict:
    """Seuil d'un mode de panne : le sujet ne donne pas de coût pour un mauvais
    diagnostic, on équilibre donc précision et rappel (F1)."""
    from sklearn.metrics import precision_recall_curve

    prec, rec, thr = precision_recall_curve(y, proba)
    f1 = 2 * prec[:-1] * rec[:-1] / np.maximum(prec[:-1] + rec[:-1], 1e-12)
    i = int(np.argmax(f1))
    return {"threshold": float(thr[i]), "f1": float(f1[i]),
            "precision": float(prec[i]), "recall": float(rec[i])}
