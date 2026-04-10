"""
Octobot Cache Manager — In-memory async cache with TTL expiration and LRU eviction.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Any, Optional


class CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: int) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def is_expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class CacheManager:
    """
    Thread-safe async LRU cache with per-entry TTL.

    Supports namespaced keys, bulk invalidation, and periodic cleanup.
    """

    def __init__(self, ttl: int = 300, max_size: int = 5000) -> None:
        self._default_ttl = ttl
        self._max_size = max_size
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired:
                del self._store[key]
                self._misses += 1
                return None
            # Move to end (LRU order)
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            effective_ttl = ttl if ttl is not None else self._default_ttl
            self._store[key] = CacheEntry(value, effective_ttl)
            self._store.move_to_end(key)
            # Evict oldest if over capacity
            while len(self._store) > self._max_size:
                evicted_key = next(iter(self._store))
                del self._store[evicted_key]
                self._evictions += 1

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def delete_namespace(self, prefix: str) -> int:
        """Delete all keys starting with the given prefix."""
        async with self._lock:
            keys = [k for k in list(self._store.keys()) if k.startswith(prefix)]
            for key in keys:
                del self._store[key]
            return len(keys)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        async with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired]
            for key in expired:
                del self._store[key]
            return len(expired)

    async def exists(self, key: str) -> bool:
        val = await self.get(key)
        return val is not None

    async def get_or_set(
        self,
        key: str,
        factory,
        ttl: Optional[int] = None,
    ) -> Any:
        """Get cached value or compute and cache it."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        await self.set(key, value, ttl=ttl)
        return value

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": round(hit_rate, 1),
        }
