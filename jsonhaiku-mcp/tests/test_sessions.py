"""Tests for the session store."""

from __future__ import annotations

import threading
import time

import pytest
from jsonhaiku.explorer import JsonHaiku

from jsonhaiku_mcp.sessions import SessionStore

SAMPLE_DATA = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]


class TestSessionLifecycle:
    def test_create_returns_prefixed_id(self):
        store = SessionStore()
        sid = store.create(JsonHaiku(SAMPLE_DATA))
        assert sid.startswith("js_")
        assert len(sid) == 11  # "js_" + 8 hex chars

    def test_get_returns_explorer(self):
        store = SessionStore()
        explorer = JsonHaiku(SAMPLE_DATA)
        sid = store.create(explorer)
        assert store.get(sid) is explorer

    def test_get_unknown_raises(self):
        store = SessionStore()
        with pytest.raises(KeyError, match="Unknown or expired"):
            store.get("js_nonexist")

    def test_remove_returns_true(self):
        store = SessionStore()
        sid = store.create(JsonHaiku(SAMPLE_DATA))
        assert store.remove(sid) is True

    def test_remove_unknown_returns_false(self):
        store = SessionStore()
        assert store.remove("js_nonexist") is False

    def test_get_after_remove_raises(self):
        store = SessionStore()
        sid = store.create(JsonHaiku(SAMPLE_DATA))
        store.remove(sid)
        with pytest.raises(KeyError, match="Unknown or expired"):
            store.get(sid)

    def test_active_count(self):
        store = SessionStore()
        assert store.active_count() == 0
        sid1 = store.create(JsonHaiku(SAMPLE_DATA))
        assert store.active_count() == 1
        store.create(JsonHaiku(SAMPLE_DATA))
        assert store.active_count() == 2
        store.remove(sid1)
        assert store.active_count() == 1


class TestTTL:
    def test_expired_session_is_purged(self):
        store = SessionStore(ttl_s=0.05)
        sid = store.create(JsonHaiku(SAMPLE_DATA))
        time.sleep(0.1)
        with pytest.raises(KeyError, match="Unknown or expired"):
            store.get(sid)

    def test_access_refreshes_ttl(self):
        store = SessionStore(ttl_s=0.15)
        sid = store.create(JsonHaiku(SAMPLE_DATA))
        time.sleep(0.08)
        store.get(sid)
        time.sleep(0.08)
        # Should still be alive — last access was 0.08s ago
        assert store.get(sid) is not None

    def test_active_count_after_expiry(self):
        store = SessionStore(ttl_s=0.05)
        store.create(JsonHaiku(SAMPLE_DATA))
        time.sleep(0.1)
        assert store.active_count() == 0


class TestConcurrency:
    def test_concurrent_creates(self):
        store = SessionStore()
        ids: list[str] = []
        lock = threading.Lock()

        def create():
            sid = store.create(JsonHaiku(SAMPLE_DATA))
            with lock:
                ids.append(sid)

        threads = [threading.Thread(target=create) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(ids) == 20
        assert len(set(ids)) == 20
        assert store.active_count() == 20

    def test_two_sessions_dont_interfere(self):
        store = SessionStore()
        data_a = [{"x": 1}]
        data_b = [{"y": 2}]
        sid_a = store.create(JsonHaiku(data_a))
        sid_b = store.create(JsonHaiku(data_b))

        ov_a = store.get(sid_a).overview()
        ov_b = store.get(sid_b).overview()

        assert ov_a["top_keys"] == ["x"]
        assert ov_b["top_keys"] == ["y"]
