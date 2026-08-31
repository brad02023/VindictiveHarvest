from __future__ import annotations

import asyncio

from PySide6.QtCore import QThread, Signal

from viha.core.harvest import harvest_async
from viha.core.models import Case, Seed


class HarvestWorker(QThread):
    log_line = Signal(str)
    finished_case = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        seed: Seed,
        selected: list[str] | None = None,
        into: Case | None = None,
    ) -> None:
        super().__init__()
        self._seed = seed
        self._selected = selected
        self._into = into

    def run(self) -> None:
        try:
            case = asyncio.run(
                harvest_async(
                    self._seed,
                    selected=self._selected,
                    on_log=self.log_line.emit,
                    into=self._into,
                )
            )
            self.finished_case.emit(case)
        except Exception as exc:
            self.failed.emit(str(exc))
