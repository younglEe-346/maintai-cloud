"""Quel modèle utilise une usine ?

Pour l'instant : le modèle commun pour toutes les usines.
(Le plan Pro pourra utiliser le modèle réentraîné sur les données de l'usine.)
"""
from sqlalchemy.orm import Session

from app.ml.predictor import get_artifact
from app.models.models import Organization


def model_for_org(org: Organization, db: Session) -> dict:
    return get_artifact()
