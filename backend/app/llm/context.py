from contextvars import ContextVar

current_task: ContextVar[str] = ContextVar("current_task", default="")
