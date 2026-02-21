"""Lumos Backend — In-memory cache with TTL"""

import time
import logging
from typing import Any, Optional

logger = logging.getLogger("lumos.cache")


class TTLCache:
    """Simple in-memory cache with per-key TTL and max-size eviction."""

    def __init__(self, default_ttl: int = 3600, max_size: int = 500):
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._last_evict = 0.0

    def _maybe_evict(self):
        """Evict expired entries lazily (at most once per 60s)."""
        now = time.time()
        if now - self._last_evict < 60:
            return
        self._last_evict = now
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    def get(self, key: str) -> Optional[Any]:
        self._maybe_evict()
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        # Enforce max size — evict oldest entries first
        if len(self._store) >= self._max_size and key not in self._store:
            self._maybe_evict()
            # If still over limit, drop earliest-expiring entries
            while len(self._store) >= self._max_size:
                oldest_key = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest_key]
        expires_at = time.time() + (ttl or self._default_ttl)
        self._store[key] = (value, expires_at)

    def clear(self):
        self._store.clear()

    def evict_expired(self):
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]


# Shared caches with different TTLs
fbi_cache = TTLCache(default_ttl=86400)       # 24 hours — FBI data rarely changes
city_cache = TTLCache(default_ttl=1800)        # 30 min — city open data
weather_cache = TTLCache(default_ttl=900)      # 15 min — weather alerts
census_cache = TTLCache(default_ttl=604800)    # 7 days — census data
state_cache = TTLCache(default_ttl=604800)     # 7 days — reverse geocode state
poi_cache = TTLCache(default_ttl=86400)        # 24 hours — nearby POIs
historical_cache = TTLCache(default_ttl=86400) # 24 hours — historical data
