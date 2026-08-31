from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SETTINGS_DIR = Path.home() / ".viha"
SETTINGS_PATH = SETTINGS_DIR / "settings.json"

DEFAULTS = {
    "github_token": "",
    "fec_api_key": "DEMO_KEY",
}


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)
    out = dict(DEFAULTS)
    out.update({k: data.get(k, v) for k, v in DEFAULTS.items()})
    return out


def save_settings(data: dict[str, Any]) -> Path:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    merged = load_settings()
    merged.update(data)
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return SETTINGS_PATH
