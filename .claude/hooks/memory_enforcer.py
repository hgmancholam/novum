#!/usr/bin/env python3
"""Stop — verify decisions-history.md was updated if any writes happened.

Compares decisions-history.md mtime against the session start timestamp
written by lint_gate.py on the first Write/Edit of the session.
Exits 2 to reactivate Claude and prompt it to update the memory bank.
Cleans up session state files on exit.
"""
import os
import sys

SESSION_FILES = [
    ".claude/session.timestamp",
    ".claude/session.has_writes",
    ".claude/session.eval_warned",
]
DECISIONS = ".github/memory-bank/logs/decisions-history.md"
MARKER = ".claude/session.timestamp"
HAS_WRITES = ".claude/session.has_writes"


def cleanup():
    for path in SESSION_FILES:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


# Skip if no writes happened this session (read-only run)
if not os.path.exists(HAS_WRITES):
    cleanup()
    sys.exit(0)

if not os.path.exists(MARKER) or not os.path.exists(DECISIONS):
    cleanup()
    sys.exit(0)

session_start = float(open(MARKER).read().strip())
decisions_mtime = os.path.getmtime(DECISIONS)

cleanup()

if decisions_mtime < session_start:
    print("MEMORY PROTOCOL — decisions-history.md no fue actualizado en esta sesión.")
    print(
        "Actualiza .github/memory-bank/logs/decisions-history.md con la decisión"
        " tomada antes de cerrar."
    )
    sys.exit(2)

sys.exit(0)
