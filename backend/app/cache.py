import os
import json
from typing import List, Optional

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# decode_responses=True => redis returns strings instead of bytes
_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
)

TICKET_LIST_KEY = "tickets:all"
TICKET_LIST_TTL = 60  # seconds (poți schimba ușor pentru teste)


def _safe_redis_call(fn, default=None):
    """
    Wrapper simplu: dacă Redis nu e accesibil, nu dăm fail aplicației,
    doar logăm și continuăm fără cache.
    """
    try:
        return fn()
    except Exception as e:
        print(f"[CACHE] Redis error: {e}")
        return default


def get_ticket_list_from_cache() -> Optional[List[dict]]:
    def _get():
        data = _client.get(TICKET_LIST_KEY)
        if data is None:
            return None
        return json.loads(data)

    return _safe_redis_call(_get, default=None)


def set_ticket_list_cache(tickets: List[dict]) -> None:
    def _set():
        _client.set(TICKET_LIST_KEY, json.dumps(tickets), ex=TICKET_LIST_TTL)
        return None

    _safe_redis_call(_set)


def invalidate_ticket_list_cache() -> None:
    def _del():
        _client.delete(TICKET_LIST_KEY)
        return None

    _safe_redis_call(_del)
