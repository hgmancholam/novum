#!/usr/bin/env python3
"""PostToolUse(Write|Edit) — warn once when an eval-trigger path is touched.

Trigger paths (from workflow.yaml F3.5 gate):
  backend/app/{agent,llm,stopping,confidence,source_plugins}/**

Exits 0 (informational only — does not block the write).
Warns only once per session to avoid noise.
"""
import json
import os
import re
import sys

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")

TRIGGER = re.compile(
    r"backend[/\\]app[/\\](agent|llm|stopping|confidence|source_plugins)[/\\]"
)

if not TRIGGER.search(file_path):
    sys.exit(0)

# Emit the warning at most once per session
warned = ".claude/session.eval_warned"
if os.path.exists(warned):
    sys.exit(0)
open(warned, "w").close()

rel = os.path.relpath(file_path) if os.path.isabs(file_path) else file_path
print(f"EVAL-GATE — '{rel}' toca un path de trigger F3.5.")
print("Antes de pasar a F4 (Review), ejecuta /eval con la hipótesis registrada.")
print(
    "Si no hay hipótesis, créala en docs/evaluation/hypotheses/ antes de continuar."
)
sys.exit(0)
