#!/usr/bin/env bash
# Vérification avant commit : tests + démarrage complet avec docker compose.
# Usage : bash scripts/verifier.sh            (tests dans Docker)
#         TESTS=local bash scripts/verifier.sh (tests avec le venv local, moins de mémoire)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1. Démarrage : docker compose up --build"
docker compose up -d --build >/dev/null 2>&1 || { docker compose up -d --build; exit 1; }

echo "== 2. Tests (base de test séparée maintai_test)"
if [ "${TESTS:-docker}" = "local" ]; then
  # mode allégé (moins de mémoire) : pytest avec le venv local, contre postgres/redis de Docker
  "${PYTHON:-venv/Scripts/python.exe}" -m pytest -q
else
  docker compose --profile tools run --rm --build tests
fi

echo "== 3. Services"
status=$(docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' maintai_migrate)
[ "$status" = "exited 0" ] || { echo "ÉCHEC : migrate = $status"; docker compose logs migrate | tail -20; exit 1; }
echo "migrate : terminé sans erreur"
for c in maintai_api maintai_worker maintai_postgres maintai_redis maintai_mailpit; do
  s=$(docker inspect -f '{{.State.Status}}' "$c")
  [ "$s" = "running" ] || { echo "ÉCHEC : $c = $s"; docker logs "$c" 2>&1 | tail -20; exit 1; }
  echo "$c : running"
done

echo "== 4. L'API répond"
for i in $(seq 1 30); do
  if curl -fs http://localhost:8000/ >/dev/null; then echo "API OK"; break; fi
  [ "$i" = 30 ] && { echo "ÉCHEC : l'API ne répond pas"; docker compose logs api | tail -30; exit 1; }
  sleep 1
done
echo "== TOUT EST OK"
