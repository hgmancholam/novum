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


# ---------------------------------------------------------------------------
# subscribe / unsubscribe / publish (IP-19 T3) — live event fan-out for runner.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_returns_bounded_queue(manager: ConnectionManager) -> None:
    from app.sse.manager import _QUEUE_MAXSIZE

    run_id = uuid4()
    q = manager.subscribe(run_id)
    assert q.maxsize == _QUEUE_MAXSIZE
    assert q.empty()


@pytest.mark.asyncio
async def test_unsubscribe_is_idempotent_and_cleans_empty_bucket(
    manager: ConnectionManager,
) -> None:
    run_id = uuid4()
    q1 = manager.subscribe(run_id)
    q2 = manager.subscribe(run_id)

    manager.unsubscribe(run_id, q1)
    manager.unsubscribe(run_id, q1)  # second call: no-op (already gone)
    manager.unsubscribe(run_id, q2)
    # Bucket cleaned up entirely.
    assert run_id not in manager._subscribers  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_publish_fans_out_to_all_subscribers(
    manager: ConnectionManager,
) -> None:
    run_id = uuid4()
    q1 = manager.subscribe(run_id)
    q2 = manager.subscribe(run_id)

    event = {"type": "QuestionAsked", "step_index": 1}
    await manager.publish(run_id, event)

    assert q1.get_nowait() == event
    assert q2.get_nowait() == event


@pytest.mark.asyncio
async def test_publish_drops_oldest_when_queue_full(
    manager: ConnectionManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrink the cap so the test stays fast and intent-revealing.
    monkeypatch.setattr("app.sse.manager._QUEUE_MAXSIZE", 2)

    run_id = uuid4()
    q = manager.subscribe(run_id)

    await manager.publish(run_id, {"step_index": 1})
    await manager.publish(run_id, {"step_index": 2})
    # Queue is now full; publishing again must drop the oldest (step_index=1).
    await manager.publish(run_id, {"step_index": 3})

    assert q.get_nowait() == {"step_index": 2}
    assert q.get_nowait() == {"step_index": 3}
    assert q.empty()
