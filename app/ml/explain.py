"""Contributions des mesures à une décision (valeurs de Shapley exactes).

Idée : on part d'une machine de référence "fonctionnement normal" (médiane des
cycles sans panne), puis on remplace ses mesures par celles de la machine réelle.
La contribution d'une mesure = de combien elle fait monter (ou baisser) le risque,
en moyenne sur tous les ordres possibles de remplacement.
Avec 5 mesures il n'y a que 2^5 = 32 combinaisons : le calcul est exact,
et les contributions s'additionnent exactement : risque_référence + somme = risque.
"""
from math import factorial

import numpy as np
import pandas as pd

from app.ml.features import RAW_FEATURES

LABELS = {
    "air_temp": ("Température air", "K"),
    "process_temp": ("Température process", "K"),
    "rotational_speed": ("Vitesse de rotation", "tr/min"),
    "torque": ("Couple", "N·m"),
    "tool_wear": ("Usure outil", "min"),
}


def shapley_contributions(predict, X: pd.DataFrame, reference: dict) -> tuple[np.ndarray, float]:
    """Renvoie (matrice n x 5 des contributions, risque de la machine de référence)."""
    d = len(RAW_FEATURES)
    x = X[RAW_FEATURES].to_numpy(dtype=float)
    ref = np.array([reference[f] for f in RAW_FEATURES], dtype=float)
    n = len(x)

    # masque k : bit j à 1 = la mesure j vient de la machine réelle, sinon de la référence
    masks = [np.array([(k >> j) & 1 for j in range(d)], dtype=bool) for k in range(2 ** d)]
    rows = np.vstack([np.where(m, x, ref) for m in masks])  # 32 x n lignes, une seule prédiction
    v = predict(pd.DataFrame(rows, columns=RAW_FEATURES)).reshape(2 ** d, n)

    phi = np.zeros((n, d))
    for j in range(d):
        for k, m in enumerate(masks):
            if m[j]:
                continue
            s = int(m.sum())
            weight = factorial(s) * factorial(d - s - 1) / factorial(d)
            phi[:, j] += weight * (v[k | (1 << j)] - v[k])
    return phi, float(v[0, 0])  # masque 0 = la référence seule


def describe(values: dict, contributions: dict, reference: dict, top: int = 2) -> str:
    """Phrase courte pour le technicien : les mesures qui font le plus monter le risque."""
    up = sorted((f for f in contributions if contributions[f] > 0.005),
                key=contributions.get, reverse=True)[:top]
    if not up:
        return "Aucune mesure ne s'écarte du fonctionnement normal."
    parts = []
    for f in up:
        label, unit = LABELS[f]
        parts.append(f"{label} {values[f]:g} {unit} (normal {reference[f]:g}) : "
                     f"+{contributions[f] * 100:.0f} pts")
    return " ; ".join(parts)
