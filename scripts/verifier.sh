#!/usr/bin/env bash
# Vérification avant commit : tests + démarrage complet avec docker compose.
# Usage : bash scripts/verifier.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1. Démarrage : docker compose up --build"
docker compose up -d --build >/dev/null 2>&1 || { docker compose up -d --build; exit 1; }

echo "== 2. Tests (dans l'image Docker, base de test séparée)"
docker compose --profile tools run --rm --build tests

echo "== 3. Services"
status=$(docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' maintai_migrate)
[ "$status" = "exited 0" ] || { echo "ÉCHEC : migrate = $status"; docker compose logs migrate | tail -20; exit 1; }
echo "migrate : terminé sans erreur"
for c in maintai_api maintai_worker maintai_postgres maintai_redis; do
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
