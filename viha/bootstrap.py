from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MIN_VERSION = (3, 10)
PACKAGES = ("httpx", "PySide6")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _pip_install(args: list[str]) -> None:
    cmd = [sys.executable, "-m", "pip", "install", *args]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        subprocess.check_call(cmd + ["--user"])


def ensure_runtime(*, gui: bool = True) -> None:
    """Install missing runtime deps into the current interpreter."""
    if sys.version_info < MIN_VERSION:
        need = ".".join(str(p) for p in MIN_VERSION)
        have = ".".join(str(p) for p in sys.version_info[:3])
        sys.stderr.write(f"VIHA needs Python {need} or newer. This interpreter is {have}.\n")
        sys.stderr.write("Install Python 3.10+ from https://www.python.org/downloads/ then run install.bat\n")
        raise SystemExit(1)

    missing: list[str] = []
    try:
        import httpx  # noqa: F401
    except ImportError:
        missing.append("httpx>=0.27")
    if gui:
        try:
            import PySide6  # noqa: F401
        except ImportError:
            missing.append("PySide6>=6.6")
    if not missing:
        return

    root = project_root()
    print("Installing VIHA dependencies…", flush=True)
    if (root / "pyproject.toml").exists():
        _pip_install(["-e", str(root)])
    else:
        _pip_install(missing)
