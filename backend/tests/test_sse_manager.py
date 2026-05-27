"""Unit tests for ``app.sse.manager.ConnectionManager`` (IP-10 §4.5)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.sse.manager import ConnectionManager, connection_manager


@pytest.fixture
def manager() -> ConnectionManager:
    """A fresh manager for each test, isolated from the module singleton."""
    return ConnectionManager()


def test_connect_increments_active_count(manager: ConnectionManager) -> None:
    run_id = uuid4()
    assert manager.active_connections(run_id) == 0
    manager.connect(run_id, "conn-1")
    assert manager.active_connections(run_id) == 1
    manager.connect(run_id, "conn-2")
    assert manager.active_connections(run_id) == 2


def test_disconnect_decrements_and_cleans_up(manager: ConnectionManager) -> None:
    run_id = uuid4()
    manager.connect(run_id, "conn-1")
    manager.connect(run_id, "conn-2")
    manager.disconnect(run_id, "conn-1")
    assert manager.active_connections(run_id) == 1
    manager.disconnect(run_id, "conn-2")
    assert manager.active_connections(run_id) == 0


def test_disconnect_unknown_is_idempotent(manager: ConnectionManager) -> None:
    run_id = uuid4()
    # Disconnect before any connect: no-op, no exception.
    manager.disconnect(run_id, "ghost")
    manager.connect(run_id, "conn-1")
    # Disconnect twice: still safe.
    manager.disconnect(run_id, "conn-1")
    manager.disconnect(run_id, "conn-1")
    assert manager.active_connections(run_id) == 0


def test_cancel_sets_flag(manager: ConnectionManager) -> None:
    run_id = uuid4()
    assert manager.is_cancelled(run_id) is False
    manager.cancel(run_id)
    assert manager.is_cancelled(run_id) is True


def test_cancel_is_idempotent(manager: ConnectionManager) -> None:
    run_id = uuid4()
    manager.cancel(run_id)
    manager.cancel(run_id)
    assert manager.is_cancelled(run_id) is True


def test_clear_cancelled_resets_flag(manager: ConnectionManager) -> None:
    run_id = uuid4()
    manager.cancel(run_id)
    manager.clear_cancelled(run_id)
    assert manager.is_cancelled(run_id) is False


def test_reset_drops_all_state(manager: ConnectionManager) -> None:
    run_a = uuid4()
    run_b = uuid4()
    manager.connect(run_a, "c1")
    manager.cancel(run_b)
    manager.reset()
    assert manager.active_connections(run_a) == 0
    assert manager.is_cancelled(run_b) is False


def test_module_singleton_is_connection_manager_instance() -> None:
    assert isinstance(connection_manager, ConnectionManager)
