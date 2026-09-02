"""Vindictive Harvest (VIHA) — local public-source OSINT workbench."""

from __future__ import annotations

import sys

__version__ = "0.1.0"
__app_name__ = "Vindictive Harvest"
__app_short__ = "VIHA"
# Distinct from other pythonw apps (Panelroom, etc.) on the Windows taskbar.
__app_user_model_id__ = "VIHA.VindictiveHarvest.1"


def claim_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(__app_user_model_id__)
    except Exception:
        pass
