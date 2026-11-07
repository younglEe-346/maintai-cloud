"""Hystérésis des alertes : évite qu'une alerte s'ouvre et se ferme sans arrêt.

- Ouverture : K mesures d'affilée avec risque >= seuil haut (le seuil de coût).
- Fermeture : K' mesures d'affilée avec risque < seuil bas (plus bas que le seuil haut).
- Entre les deux seuils (zone morte) : rien ne change, et les deux compteurs repartent à 0.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HysteresisConfig:
    high: float      # seuil d'ouverture
    low: float       # seuil de fermeture
    open_k: int = 3
    close_k: int = 3

    def __post_init__(self):
        # cas limite : seuil haut = 0 ("alerter sur tout", ratio de coût énorme) -> seuil bas = 0
        if not (0 <= self.low < self.high or self.low == self.high == 0):
            raise ValueError(f"Il faut 0 <= seuil bas < seuil haut (reçu bas={self.low}, haut={self.high})")
        if self.open_k < 1 or self.close_k < 1:
            raise ValueError("open_k et close_k doivent valoir au moins 1")


@dataclass
class Counters:
    high: int = 0  # mesures consécutives >= seuil haut
    low: int = 0   # mesures consécutives < seuil bas


def step(counters: Counters, risk: float, cfg: HysteresisConfig, alert_active: bool) -> str | None:
    """Prend en compte une mesure. Renvoie "open", "close" ou None."""
    if risk >= cfg.high:
        counters.high += 1
        counters.low = 0
    elif risk < cfg.low:
        counters.low += 1
        counters.high = 0
    else:
        counters.high = 0
        counters.low = 0

    if not alert_active and counters.high >= cfg.open_k:
        return "open"
    if alert_active and counters.low >= cfg.close_k:
        return "close"
    return None
