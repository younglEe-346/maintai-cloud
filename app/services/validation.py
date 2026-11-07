"""Validation d'une mesure reçue : format, puis valeurs physiquement possibles.

On ne rejette que l'IMPOSSIBLE (ex. couple négatif, température de 900 K).
L'INHABITUEL (ex. couple très élevé) est accepté : c'est justement le rôle du
modèle de le détecter comme un risque de panne.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

FailureMode = Literal["TWF", "HDF", "PWF", "OSF", "RNF"]

# bornes physiques : (min, max, unité)
PHYSICAL_BOUNDS = {
    "air_temp": (200.0, 400.0, "K"),
    "process_temp": (200.0, 500.0, "K"),
    "rotational_speed": (0.0, 10_000.0, "tr/min"),
    "torque": (0.0, 500.0, "N·m"),
    "tool_wear": (0.0, 1_000.0, "min"),
}

MAX_BATCH_SIZE = 1000


class Label(BaseModel):
    """Retour terrain : la machine est-elle tombée en panne, et de quel(s) mode(s) ?"""
    failure: bool
    modes: list[FailureMode] = []


class MeasureIn(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)  # NaN et infini refusés

    message_id: str = Field(min_length=1, max_length=128)
    timestamp: Optional[datetime] = None  # heure de la mesure ; par défaut : heure de réception
    air_temp: float
    process_temp: float
    rotational_speed: float
    torque: float
    tool_wear: float
    label: Optional[Label] = None


_PYDANTIC_MESSAGES = {
    "missing": "champ obligatoire manquant",
    "float_parsing": "doit être un nombre",
    "float_type": "doit être un nombre",
    "finite_number": "doit être un nombre fini (pas NaN ni infini)",
    "string_too_short": "ne doit pas être vide",
    "string_too_long": "trop long (128 caractères maximum)",
    "string_type": "doit être un texte",
    "datetime_parsing": "date invalide (format ISO 8601 attendu)",
    "datetime_from_date_parsing": "date invalide (format ISO 8601 attendu)",
    "literal_error": "mode inconnu (TWF, HDF, PWF, OSF ou RNF)",
    "bool_parsing": "doit être vrai ou faux",
    "model_type": "doit être un objet JSON",
}


def check_measure(raw) -> tuple[Optional[MeasureIn], list[str]]:
    """Renvoie (mesure validée, []) ou (None, [raisons du rejet en français])."""
    if not isinstance(raw, dict):
        return None, ["la mesure doit être un objet JSON"]
    try:
        m = MeasureIn.model_validate(raw)
    except ValidationError as e:
        reasons = []
        for err in e.errors():
            field = ".".join(str(p) for p in err["loc"]) or "mesure"
            reasons.append(f"{field} : {_PYDANTIC_MESSAGES.get(err['type'], err['msg'])}")
        return None, reasons

    reasons = []
    for field, (lo, hi, unit) in PHYSICAL_BOUNDS.items():
        value = getattr(m, field)
        if not lo <= value <= hi:
            reasons.append(f"{field} = {value:g} {unit} : physiquement impossible "
                           f"(plage acceptée [{lo:g} ; {hi:g}] {unit})")
    if reasons:
        return None, reasons

    if m.timestamp is not None and m.timestamp.tzinfo is not None:
        m.timestamp = m.timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    return m, []


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
