"""Limite des tentatives de connexion : échecs comptés par e-mail, dans Redis.

Clé « login_fail:<e-mail> » : INCR compte les échecs, EXPIRE l'efface après la fenêtre (15 min par défaut,
comptée depuis le premier échec). L'e-mail est compté qu'il existe ou non : on ne révèle pas quels comptes existent.
Si Redis est injoignable, on laisse passer (la connexion reste disponible) et on écrit un avertissement.
"""
import logging
import math

import redis
from fastapi import HTTPException

from app.config import LOGIN_MAX_FAILURES, LOGIN_WINDOW_MINUTES
from app.services.usage import _redis

log = logging.getLogger(__name__)


def _key(email: str) -> str:
    return f"login_fail:{email.strip().lower()}"


def check_not_blocked(email: str) -> None:
    """À appeler AVANT de vérifier le mot de passe : un compte bloqué ne fait aucun calcul bcrypt."""
    try:
        r = _redis()
        failures = int(r.get(_key(email)) or 0)
        if failures < LOGIN_MAX_FAILURES:
            return
        ttl = r.ttl(_key(email))
        if ttl == -1:  # sécurité : une clé sans expiration bloquerait le compte pour toujours
            r.expire(_key(email), LOGIN_WINDOW_MINUTES * 60)
    except redis.RedisError:
        log.warning("Redis injoignable : limite de connexion ignorée")
        return
    wait = max(ttl, 1) if ttl is not None and ttl > 0 else LOGIN_WINDOW_MINUTES * 60
    minutes = math.ceil(wait / 60)
    raise HTTPException(
        status_code=429,
        detail=f"Trop de tentatives, réessayez dans {minutes} minute{'s' if minutes > 1 else ''}",
        headers={"Retry-After": str(wait)},
    )


def record_failure(email: str) -> None:
    try:
        r = _redis()
        key = _key(email)
        if r.incr(key) == 1:  # premier échec : la fenêtre démarre
            r.expire(key, LOGIN_WINDOW_MINUTES * 60)
    except redis.RedisError:
        log.warning("Redis injoignable : échec de connexion non compté")


def reset(email: str) -> None:
    try:
        _redis().delete(_key(email))
    except redis.RedisError:
        log.warning("Redis injoignable : compteur de connexion non remis à zéro")
