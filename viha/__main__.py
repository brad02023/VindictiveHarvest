from __future__ import annotations

import sys

from viha.bootstrap import ensure_runtime

_GUI_CMDS = {"reap", "ingest-html"}
_need_gui = not any(arg in _GUI_CMDS for arg in sys.argv[1:])
ensure_runtime(gui=_need_gui)

from viha.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
