from __future__ import annotations
from typing import Dict, Any, Optional
from threading import RLock
from dataclasses import dataclass, field
import time

@dataclass
class _CacheEntry:
    data: Any
    ts: float = field(default_factory=time.time)

class CatalogCache:
    """
    Caché de catálogos a nivel aplicación.
    - Thread-safe (lock)
    - Sin TTL por defecto; podés invalidar por evento (alta/edición)
    """
    _instance: "CatalogCache" = None
    _lock = RLock()

    def __init__(self):
        self._data: Dict[str, _CacheEntry] = {}
        self._loaded_once: bool = False

    @classmethod
    def get(cls) -> "CatalogCache":
        with cls._lock:
            if cls._instance is None:
                cls._instance = CatalogCache()
            return cls._instance

    def set(self, key: str, value: Any):
        with self._lock:
            self._data[key] = _CacheEntry(value)
            self._loaded_once = True

    def get_value(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            return entry.data if entry else None

    def has_all(self, keys: list[str]) -> bool:
        with self._lock:
            return all(k in self._data for k in keys)

    def mark_loaded(self):
        with self._lock:
            self._loaded_once = True

    def loaded_once(self) -> bool:
        with self._lock:
            return self._loaded_once

    def invalidate(self, *keys: str):
        with self._lock:
            if not keys:
                self._data.clear()
                self._loaded_once = False
            else:
                for k in keys:
                    self._data.pop(k, None)
