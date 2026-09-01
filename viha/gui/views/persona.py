from __future__ import annotations

from collections import defaultdict

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from viha.collectors.people import people_index_urls
from viha.core.identity import persona_brief
from viha.core.models import Case, Fact
from viha.gui.theme import AMBER, BONE, GREEN, MUTED, RUST

SECTION_ORDER = [
    ("identity", "IDENTITY"),
    ("contact", "CONTACT"),
    ("social", "SOCIAL"),
    ("legal", "LEGAL"),
    ("property", "PROPERTY"),
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
        self._show_hidden = False
        self.hide_btn = QPushButton("SHOW MISSES")
        self.hide_btn.clicked.connect(self._toggle_hidden)

        root.addWidget(self.header_name)
        root.addWidget(self.header_meta)
        stats_row = QHBoxLayout()
        stats_row.addWidget(self.header_stats, 1)
        stats_row.addWidget(self.hide_btn)
        root.addLayout(stats_row)

        self.sheet = QFrame()
        self.sheet.setObjectName("PersonaSheet")
        sheet_lay = QGridLayout(self.sheet)
        sheet_lay.setContentsMargins(12, 10, 12, 10)
        sheet_lay.setHorizontalSpacing(18)
        self._brief_labels: dict[str, QLabel] = {}
        captions = (
            ("age", "AGE"),
            ("dob", "DOB"),
            ("location", "POSSIBLE LOCATIONS"),
            ("job", "JOB"),
            ("relatives", "RELATIVES"),
        )
        for col, (key, caption) in enumerate(captions):
            cap = QLabel(caption)
            cap.setObjectName("PersonaKey")
            val = QLabel("—")
            val.setObjectName("PersonaBrief")
            val.setWordWrap(True)
            val.setMinimumHeight(40)
            val.setMinimumWidth(90)
            val.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            val.setAutoFillBackground(False)
            val.setStyleSheet(f"background: transparent; color: {BONE}; font-size: 14px;")
            sheet_lay.addWidget(cap, 0, col)
            sheet_lay.addWidget(val, 1, col)
            self._brief_labels[key] = val
        idx_cap = QLabel("PEOPLE INDEX")
        idx_cap.setObjectName("PersonaKey")
        self._index_label = QLabel("Enter a US phone, or name with city and state.")
        self._index_label.setObjectName("PersonaIndex")
        self._index_label.setWordWrap(True)
        self._index_label.setOpenExternalLinks(True)
        self._index_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._index_label.setMinimumHeight(28)
        sheet_lay.addWidget(idx_cap, 2, 0, 1, 5)
        sheet_lay.addWidget(self._index_label, 3, 0, 1, 5)
        self.sheet.setMinimumHeight(168)
        root.addWidget(self.sheet)

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
        hits = case.display_facts()
        hidden = case.hidden_facts()
        self.header_stats.setText(
            f"{len(hits)} hits   ·   {len(hidden)} misses/lookups/weak social hidden   ·   "
            f"{len(case.errors)} collector errors"
        )
        self.hide_btn.setText(
            f"{'HIDE' if self._show_hidden else 'SHOW'} MISSES ({len(hidden)})"
        )
        self.hide_btn.setEnabled(bool(hidden))
        self._fill_brief(case)
        self._fill_people_index(case)

        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        grouped: dict[str, list[Fact]] = defaultdict(list)
        for fact in hits:
            if fact.predicate == "people_index":
                continue
            grouped[fact.section].append(fact)
        for key, title in SECTION_ORDER:
            rows = grouped.get(key) or []
            if rows:
                self.body_layout.addWidget(self._section_table(title, rows))

        if self._show_hidden and hidden:
            self.body_layout.addWidget(
                self._section_table("MISSES / LOOKUPS (not resolved hits)", hidden, dim=True)
            )

        self.body_layout.addStretch()

    def _toggle_hidden(self) -> None:
        self._show_hidden = not self._show_hidden
        if self._case:
            self.render(self._case)

    def _fill_brief(self, case: Case) -> None:
        brief = persona_brief(case)

        def fmt(fact: Fact | None, empty: str = "—") -> str:
            if not fact:
                return empty
            mark = "  (candidate)" if fact.candidate and not fact.pinned else ""
            return f"{fact.value}{mark}"

        def fmt_many(facts: list[Fact], empty: str = "—") -> str:
            if not facts:
                return empty
            parts = []
            for fact in facts[:4]:
                mark = "  (candidate)" if fact.candidate and not fact.pinned else ""
                parts.append(f"{fact.value}{mark}")
            return "  ·  ".join(parts)

        locs = brief.get("locations") or []
        if not locs:
            loc = brief.get("address") or brief.get("location") or brief.get("gps")
            loc_txt = fmt(loc)
        else:
            loc_txt = fmt_many(locs)
        self._brief_labels["age"].setText(fmt(brief.get("age")))
        self._brief_labels["dob"].setText(fmt(brief.get("dob")))
        self._brief_labels["location"].setText(loc_txt)
        self._brief_labels["job"].setText(fmt(brief.get("job")))
        self._brief_labels["relatives"].setText(fmt_many(brief.get("relatives") or []))

    def _fill_people_index(self, case: Case) -> None:
        urls: list[tuple[str, str]] = list(people_index_urls(case.seed))
        seen = {u for _, u in urls}
        for fact in case.facts:
            href = (fact.extra or {}).get("profile_url") or fact.source.url
            if not href or href in seen:
                continue
            if "fastpeoplesearch.com" in href and "_id_G" in href:
                urls.append(("FastPeopleSearch profile", href))
                seen.add(href)
        if not urls:
            self._index_label.setText("Enter a US phone, or a name with city and state.")
            return
        parts = [f'<a href="{escape(url, quote=True)}">{escape(label)}</a>' for label, url in urls]
        hint = (
            "<span style='color:#8A8476'> — if a page 403s, save the <b>profile</b> HTML (the _id_G page) then IMPORT PEOPLE HTML</span>"
        )
        self._index_label.setText("  ·  ".join(parts) + hint)

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
