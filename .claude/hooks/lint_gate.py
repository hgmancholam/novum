#!/usr/bin/env python3
"""PostToolUse(Write|Edit) — run ruff on modified Python files.

Reads tool input from stdin (JSON). Outputs ruff errors to stdout so
Claude sees them and fixes before continuing. Exits 2 to reactivate Claude.
"""
import json
import os
import subprocess
import sys
import time

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")

# Record session start once per session
os.makedirs(".claude", exist_ok=True)
if not os.path.exists(".claude/session.timestamp"):
    with open(".claude/session.timestamp", "w") as fh:
        fh.write(str(time.time()))
open(".claude/session.has_writes", "w").close()

if not file_path.endswith(".py"):
    sys.exit(0)

SKIP = (".venv", "__pycache__", "migrations", ".pyc", "node_modules")
if any(s in file_path for s in SKIP):
    sys.exit(0)

# Prefer the backend venv's ruff; fall back to PATH
scripts_dir = "Scripts" if os.name == "nt" else "bin"
ruff_in_venv = os.path.join(
    "backend", ".venv", scripts_dir, "ruff" + (".exe" if os.name == "nt" else "")
)
ruff_cmd = ruff_in_venv if os.path.exists(ruff_in_venv) else "ruff"

result = subprocess.run(
    [ruff_cmd, "check", "--output-format=concise", file_path],
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    output = (result.stdout + result.stderr).strip()
    rel = os.path.relpath(file_path) if os.path.isabs(file_path) else file_path
    print(f"LINT GATE — ruff errors in {rel}:")
    print(output)
    print("\nFix these errors before continuing.")
    sys.exit(2)

sys.exit(0)
