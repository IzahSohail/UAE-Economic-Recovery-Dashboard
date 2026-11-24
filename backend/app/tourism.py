"""Load travel-concerns payload for the tourism section."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = ROOT / "data" / "travel_concerns.json"


def load_travel_concerns() -> dict[str, Any]:
    if not CACHE_FILE.exists():
        raise FileNotFoundError(
            f"Missing {CACHE_FILE}. Run `python backend/scripts/tourism.py` first."
        )
    return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
