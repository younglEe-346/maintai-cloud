"""Sauvegarde et chargement des modèles versionnés : models/risk_model_v<N>.joblib."""
import os
import re
from pathlib import Path

import joblib

MODELS_DIR = Path(os.getenv("MODELS_DIR", Path(__file__).resolve().parents[2] / "models"))
_PATTERN = re.compile(r"^risk_model_v(\d+)\.joblib$")


def list_versions() -> list[int]:
    if not MODELS_DIR.exists():
        return []
    return sorted(int(m.group(1)) for f in MODELS_DIR.iterdir() if (m := _PATTERN.match(f.name)))


def model_path(version: int) -> Path:
    return MODELS_DIR / f"risk_model_v{version}.joblib"


def next_version() -> int:
    versions = list_versions()
    return versions[-1] + 1 if versions else 1


def save_artifact(artifact: dict) -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = model_path(artifact["version"])
    if path.exists():
        raise FileExistsError(f"{path} existe déjà : une version publiée ne doit jamais être écrasée.")
    joblib.dump(artifact, path, compress=3)
    return path


def load_artifact(version: int | None = None) -> dict:
    """Charge la version demandée, ou la plus récente si version=None."""
    if version is None:
        versions = list_versions()
        if not versions:
            raise FileNotFoundError(
                f"Aucun modèle dans {MODELS_DIR}. Lancez d'abord : docker compose run --rm trainer"
            )
        version = versions[-1]
    return joblib.load(model_path(version))
