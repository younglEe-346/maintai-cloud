"""Compteur de mesures par usine et par jour (UTC), dans Redis.

INCRBY est atomique : même si plusieurs lots arrivent en même temps, le compteur
reste juste. La clé expire après 2 jours : pas de ménage à faire.
"""
from datetime import datetime, timedelta, timezone

import redis

from app.config import REDIS_URL

_client = None


def _redis():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL)
    return _client


def _key(org_id: str) -> str:
    return f"usage:measures:{org_id}:{datetime.now(timezone.utc):%Y-%m-%d}"


def measures_today(org_id: str) -> int:
    return int(_redis().get(_key(org_id)) or 0)


def try_reserve(org_id: str, n: int, limit: int) -> tuple[bool, int]:
    """Réserve n mesures dans le quota du jour. Renvoie (accepté, total après réservation)."""
    key = _key(org_id)
    pipe = _redis().pipeline()
    pipe.incrby(key, n)
    pipe.expire(key, 2 * 24 * 3600)
    total = pipe.execute()[0]
    if total > limit:
        _redis().decrby(key, n)  # on annule : le lot est refusé
        return False, total - n
    return True, total


def release(org_id: str, n: int) -> None:
    """Rend n mesures réservées mais finalement non enregistrées (doublons)."""
    if n > 0:
        _redis().decrby(_key(org_id), n)


def seconds_until_reset() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds()) + 1
