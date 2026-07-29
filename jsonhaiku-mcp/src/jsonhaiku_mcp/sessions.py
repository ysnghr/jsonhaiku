"""In-memory session store with TTL-based cleanup.

Each loaded JSON payload gets a short session ID that the LLM passes back on
every follow-up tool call. Sessions expire after a configurable TTL (default
one hour) and are cleaned up lazily on access.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jsonhaiku.explorer import JsonHaiku

_DEFAULT_TTL_S = 3600
_PREFIX = "js_"


@dataclass
class _Entry:
    """A single session entry."""

    explorer: JsonHaiku
    created_at: float
    last_accessed: float


@dataclass
class SessionStore:
    """Thread-safe session store with TTL-based expiration."""

    ttl_s: float = _DEFAULT_TTL_S
    _sessions: dict[str, _Entry] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def create(self, explorer: JsonHaiku) -> str:
        """Register an explorer and return a short session ID."""
        session_id = _PREFIX + uuid.uuid4().hex[:8]
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            self._sessions[session_id] = _Entry(
                explorer=explorer,
                created_at=now,
                last_accessed=now,
            )
        return session_id

    def get(self, session_id: str) -> JsonHaiku:
        """Look up a session, refreshing its last-access time.

        Raises:
            KeyError: If the session does not exist or has expired.
        """
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            entry = self._sessions.get(session_id)
            if entry is None:
                msg = f"Unknown or expired session: {session_id}"
                raise KeyError(msg)
            entry.last_accessed = now
            return entry.explorer

    def remove(self, session_id: str) -> bool:
        """Remove a session. Returns True if it existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def active_count(self) -> int:
        """Return the number of live (non-expired) sessions."""
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            return len(self._sessions)

    def _purge_expired(self, now: float) -> None:
        expired = [
            sid for sid, entry in self._sessions.items() if now - entry.last_accessed > self.ttl_s
        ]
        for sid in expired:
            del self._sessions[sid]
