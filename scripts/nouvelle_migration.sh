#!/usr/bin/env bash
# Génère une migration Alembic en comparant les modèles à une base temporaire vide
# mise à jour jusqu'à la dernière migration. Usage : bash scripts/nouvelle_migration.sh 0003 "description"
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-venv/Scripts/python.exe}
docker compose exec -T postgres psql -q -U postgres -c "DROP DATABASE IF EXISTS maintai_migration_tmp;" -c "CREATE DATABASE maintai_migration_tmp;"
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/maintai_migration_tmp
"$PY" -m alembic upgrade head
"$PY" -m alembic revision --autogenerate --rev-id "$1" -m "$2"
docker compose exec -T postgres psql -q -U postgres -c "DROP DATABASE maintai_migration_tmp;"
