from __future__ import annotations

import json
from pathlib import Path

from viha.core.models import Case

CASES_DIR = Path(__file__).resolve().parents[2] / "cases"


def ensure_cases_dir() -> Path:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    return CASES_DIR


def case_path(case: Case) -> Path:
    ensure_cases_dir()
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in case.id)
    return CASES_DIR / f"{safe}.viha"


def save_case(case: Case, path: Path | None = None) -> Path:
    dest = path or case_path(case)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(case.to_dict(), indent=2), encoding="utf-8")
    return dest


def load_case(path: Path) -> Case:
    return Case.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_cases() -> list[Path]:
    if not CASES_DIR.exists():
        return []
    return sorted(CASES_DIR.glob("*.viha"), key=lambda p: p.stat().st_mtime, reverse=True)
