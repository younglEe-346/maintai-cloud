"""Quel modèle utilise une usine ?

- Plan Pro avec un modèle réentraîné actif -> ce modèle (appris sur SES données).
- Sinon (plan Gratuit, ou pas encore de modèle) -> le modèle commun.
Les modèles d'une usine sont dans son propre dossier et ne sont jamais servis à une autre.
"""
import joblib
from sqlalchemy.orm import Session

from app.core.plans import plan_of
from app.ml.predictor import get_artifact
from app.models.models import Organization, OrgModel

_cache: dict = {}  # chemin du fichier -> modèle chargé (un fichier promu ne change jamais)


def load_org_artifact(path: str) -> dict:
    if path not in _cache:
        _cache[path] = joblib.load(path)
    return _cache[path]


def model_for_org(org: Organization, db: Session) -> dict:
    if plan_of(org)["custom_model"]:
        active = (db.query(OrgModel)
                  .filter(OrgModel.org_id == org.id, OrgModel.status == "active").first())
        if active is not None and active.path:
            return load_org_artifact(active.path)
    return get_artifact()
