"""SQLite-Cache mit TTL. Namespaces: "places_search", "places_details", "html", "vcard".

Google-Nutzungsbedingungen: Places-Inhalte außer der place_id dürfen maximal 30 Tage gecacht werden –
die TTL wird beim Lesen erzwungen (settings.places_cache_ttl_days). Cache(None) ist ein No-Op.

Werte werden zlib-komprimiert abgelegt (HTML schrumpft um Faktor 5–8). Ein bundesweiter Lauf lädt
Hunderttausende Seiten; unkomprimiert wächst die Datei sonst in den zweistelligen Gigabyte-Bereich.
Alte, unkomprimierte Einträge bleiben lesbar.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib
from pathlib import Path
from typing import Any

_DAY = 86_400.0
_GZIP_LEVEL = 6


class Cache:
    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (namespace TEXT NOT NULL, key TEXT NOT NULL,"
            " value BLOB NOT NULL, created REAL NOT NULL, PRIMARY KEY (namespace, key))"
        )
        self._conn.commit()

    @property
    def enabled(self) -> bool:
        return self._conn is not None

    def get(self, namespace: str, key: str, ttl_days: int) -> Any | None:
        if self._conn is None:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT value, created FROM cache WHERE namespace = ? AND key = ?", (namespace, key)
            ).fetchone()
        if row is None:
            return None
        value, created = row
        if time.time() - created > ttl_days * _DAY:
            return None
        try:
            return json.loads(_decode(value))
        except (json.JSONDecodeError, zlib.error, UnicodeDecodeError):
            return None

    def set(self, namespace: str, key: str, value: Any) -> None:
        if self._conn is None:
            return
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        payload = zlib.compress(json.dumps(value, ensure_ascii=False).encode("utf-8"), _GZIP_LEVEL)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (namespace, key, value, created) VALUES (?, ?, ?, ?)",
                (namespace, key, payload, time.time()),
            )
            self._conn.commit()

    def purge_expired(self, namespace: str, ttl_days: int) -> int:
        if self._conn is None:
            return 0
        cutoff = time.time() - ttl_days * _DAY
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM cache WHERE namespace = ? AND created < ?", (namespace, cutoff)
            )
            self._conn.commit()
        return cur.rowcount

    def vacuum(self) -> None:
        """Nach großen Löschaktionen den Plattenplatz wirklich freigeben."""
        if self._conn is not None:
            with self._lock:
                self._conn.execute("VACUUM")

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _decode(value: Any) -> str:
    """Komprimierte Werte auspacken; ältere Einträge liegen als Text vor."""
    if isinstance(value, bytes):
        try:
            return zlib.decompress(value).decode("utf-8")
        except zlib.error:
            return value.decode("utf-8", errors="replace")
    return value
