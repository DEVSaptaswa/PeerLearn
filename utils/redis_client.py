"""
utils/redis_client.py
Redis-backed presence system.

Key schema:
  pl:presence:<user_id>   → timestamp of last activity (UNIX float, TTL 1800 s)
  pl:status:<user_id>     → explicit status override ("invisible" / "dnd")
  pl:cache:<key>          → generic application cache

Status resolution (in order):
  1. If pl:status == "invisible"           → always show as offline
  2. If pl:presence key missing            → offline
  3. elapsed <= ACTIVE_THRESHOLD (5 min)  → active  (green)
  4. elapsed <= AWAY_THRESHOLD   (30 min) → away    (yellow)
  5. otherwise                            → offline (grey)
"""
from __future__ import annotations

import time
import logging
from typing import Literal

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

Status = Literal["active", "away", "offline"]

# ── Client singleton ───────────────────────────────────────────────────────────
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB_INDEX,
            password=getattr(settings, "REDIS_PASSWORD", None) or None,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
    return _redis_client


# ── Presence keys ──────────────────────────────────────────────────────────────
PRESENCE_TTL     = 1800
ACTIVE_THRESHOLD = getattr(settings, "PRESENCE_ACTIVE_THRESHOLD", 300)
AWAY_THRESHOLD   = getattr(settings, "PRESENCE_AWAY_THRESHOLD", 1800)

_P = "pl:presence:"
_S = "pl:status:"


def _presence_key(user_id: int | str) -> str:
    return f"{_P}{user_id}"


def _status_key(user_id: int | str) -> str:
    return f"{_S}{user_id}"


# ── Write ──────────────────────────────────────────────────────────────────────
def update_presence(user_id: int) -> None:
    """Called by middleware on every authenticated request."""
    try:
        get_redis().set(_presence_key(user_id), time.time(), ex=PRESENCE_TTL)
    except Exception as exc:
        logger.debug("Redis presence update failed: %s", exc)


def set_user_status(user_id: int, status: str) -> None:
    """
    Explicit status override.
    status ∈ {"invisible", "dnd", "clear"}
    "clear" removes the override.
    """
    try:
        r = get_redis()
        if status == "clear":
            r.delete(_status_key(user_id))
        else:
            r.set(_status_key(user_id), status, ex=PRESENCE_TTL)
    except Exception as exc:
        logger.debug("Redis set_user_status failed: %s", exc)


# ── Read ───────────────────────────────────────────────────────────────────────
def get_user_status(user_id: int) -> Status:
    try:
        r = get_redis()
        override = r.get(_status_key(user_id))
        if override == "invisible":
            return "offline"

        raw = r.get(_presence_key(user_id))
        if raw is None:
            return "offline"

        elapsed = time.time() - float(raw)
        if elapsed <= ACTIVE_THRESHOLD:
            return "active"
        if elapsed <= AWAY_THRESHOLD:
            return "away"
        return "offline"
    except Exception:
        return "offline"


def get_bulk_statuses(user_ids: list[int]) -> dict[int, Status]:
    """Efficiently batch-fetch statuses using a Redis pipeline."""
    if not user_ids:
        return {}
    try:
        r = get_redis()
        now = time.time()
        pipe = r.pipeline(transaction=False)
        for uid in user_ids:
            pipe.get(_status_key(uid))
            pipe.get(_presence_key(uid))
        results = pipe.execute()

        statuses: dict[int, Status] = {}
        for i, uid in enumerate(user_ids):
            override = results[i * 2]
            raw      = results[i * 2 + 1]
            if override == "invisible":
                statuses[uid] = "offline"
            elif raw is None:
                statuses[uid] = "offline"
            else:
                elapsed = now - float(raw)
                if elapsed <= ACTIVE_THRESHOLD:
                    statuses[uid] = "active"
                elif elapsed <= AWAY_THRESHOLD:
                    statuses[uid] = "away"
                else:
                    statuses[uid] = "offline"
        return statuses
    except Exception:
        return {uid: "offline" for uid in user_ids}


# ── Generic cache helpers ──────────────────────────────────────────────────────
def cache_set(key: str, value: str, ttl: int = 300) -> None:
    try:
        get_redis().set(f"pl:cache:{key}", value, ex=ttl)
    except Exception:
        pass


def cache_get(key: str) -> str | None:
    try:
        return get_redis().get(f"pl:cache:{key}")
    except Exception:
        return None


def cache_delete(key: str) -> None:
    try:
        get_redis().delete(f"pl:cache:{key}")
    except Exception:
        pass
