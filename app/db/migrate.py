"""Met la base à jour au démarrage : python -m app.db.migrate

Cas d'une base créée avant Alembic (par l'ancien Base.metadata.create_all) :
elle a déjà les tables mais pas de table alembic_version. On complète alors
la table predictions si elle manque, on la marque à la version 0001
(schéma initial), puis on applique les migrations suivantes.
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db.session import engine
from app.models.models import Prediction

BASELINE = "0001"


def main() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and "organizations" in tables:
        print(f"Base existante sans suivi Alembic : marquage à la version {BASELINE}.")
        Prediction.__table__.create(engine, checkfirst=True)  # absente des toutes premières bases
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    main()
