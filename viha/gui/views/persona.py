from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from viha.core.models import Case, Fact
from viha.gui.theme import AMBER, GREEN, MUTED, RUST

SECTION_ORDER = [
    ("identity", "IDENTITY"),
    ("contact", "CONTACT"),
    ("social", "SOCIAL"),
    ("legal", "LEGAL"),
    ("business", "BUSINESS"),
    ("sanctions", "WATCHLISTS"),
    ("web", "WEB"),
    ("infra", "WEB & INFRA"),
    ("recipes", "SEARCH RECIPES"),
]


class PersonaView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._case: Case | None = None
        self._on_select = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.header_name = QLabel("No persona yet")
        self.header_name.setObjectName("PersonaName")
        self.header_meta = QLabel("Enter a seed and reap public sources.")
        self.header_meta.setObjectName("Muted")
        self.header_stats = QLabel("")
        self.header_stats.setObjectName("Muted")

        root.addWidget(self.header_name)
        root.addWidget(self.header_meta)
        root.addWidget(self.header_stats)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 12, 0, 0)
        self.body_layout.addStretch()
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

    def bind_select(self, cb) -> None:
        self._on_select = cb

    def render(self, case: Case) -> None:
        self._case = case
        self.header_name.setText(case.seed.display_name())
        bits = [x for x in (case.seed.phone, case.seed.email, case.seed.org) if x]
        self.header_meta.setText("  ·  ".join(bits) if bits else "No contact seeds")
        visible = case.visible_facts()
        cands = case.candidates()
        self.header_stats.setText(
            f"{len(visible)} sourced facts   ·   {len(cands)} candidates   ·   "
            f"{len(case.errors)} collector errors"
        )

        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        grouped: dict[str, list[Fact]] = defaultdict(list)
        for fact in case.facts:
            grouped[fact.section].append(fact)

        if cands:
            self.body_layout.addWidget(self._section_table("CANDIDATES (unpinned)", cands, dim=True))

        for key, title in SECTION_ORDER:
            rows = [f for f in grouped.get(key, []) if not f.candidate or f.pinned]
            if rows:
                self.body_layout.addWidget(self._section_table(title, rows))

        self.body_layout.addStretch()

    def _section_table(self, title: str, facts: list[Fact], dim: bool = False) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 8, 0, 12)
        label = QLabel(title)
        label.setObjectName("Section")
        lay.addWidget(label)

        table = QTableWidget(len(facts), 4)
        table.setHorizontalHeaderLabels(["FIELD", "VALUE", "SOURCE", "CONF"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 130)
        table.setColumnWidth(1, 420)
        table.setColumnWidth(2, 160)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        table.setFixedHeight(min(360, 36 + 28 * max(1, len(facts))))

        for i, fact in enumerate(facts):
            items = [
                QTableWidgetItem(fact.predicate),
                QTableWidgetItem(fact.value),
                QTableWidgetItem(fact.source.publisher),
                QTableWidgetItem(f"{fact.confidence:.2f}"),
            ]
            color = MUTED if dim else (GREEN if fact.confidence >= 0.7 else AMBER if fact.confidence >= 0.45 else RUST)
            for col, item in enumerate(items):
                item.setForeground(_qcolor(color))
                item.setData(Qt.ItemDataRole.UserRole, fact.id)
                table.setItem(i, col, item)

        def picked():
            row = table.currentRow()
            if row < 0 or not self._on_select:
                return
            fact_id = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            fact = next((f for f in facts if f.id == fact_id), None)
            if fact:
                self._on_select(fact)

        table.itemSelectionChanged.connect(picked)
        lay.addWidget(table)
        return wrap


def _qcolor(hex_color: str):
    from PySide6.QtGui import QColor

    return QColor(hex_color)
