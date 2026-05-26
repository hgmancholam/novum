#!/usr/bin/env python3
"""
Export Pydantic models to TypeScript types.

Generates frontend/src/types/events.ts from backend Pydantic models.
Run this whenever backend event models change.

Usage:
    python scripts/export_types.py
"""

import json
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))


def main() -> None:
    """Export Pydantic models to TypeScript."""
    output_path = Path(__file__).parent.parent / "frontend" / "src" / "types" / "events.ts"

    # TODO: Import actual models when they exist (BRD-02)
    # from app.models.events import RunEvent, StopReason, etc.
    # schema = model.model_json_schema()

    print(f"Type export placeholder - output would go to: {output_path}")
    print("Run after BRD-02 (Domain Models) is implemented.")


if __name__ == "__main__":
    main()
