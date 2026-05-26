"""Custom HTTP exceptions for the API surface."""

from __future__ import annotations

from fastapi import HTTPException, status


class RunNotFoundError(HTTPException):
    """Run does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )


class EventNotFoundError(HTTPException):
    """Event does not exist."""

    def __init__(self, event_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )


class RunNotForkableError(HTTPException):
    """Run cannot be forked from this event (RF-03)."""

    def __init__(self, event_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is not a forkable point",
        )


class RunAlreadyStoppedError(HTTPException):
    """Run has already stopped and the requested transition is invalid."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run {run_id} has already stopped",
        )


class RunStillRunningError(HTTPException):
    """Run is still running (cannot resume)."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Run {run_id} is still running",
        )


class UnauthorizedError(HTTPException):
    """User not authorized for this operation."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )
