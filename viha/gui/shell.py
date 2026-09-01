from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from viha import __app_name__, __app_short__, __version__
from viha.collectors.registry import COLLECTORS
from viha.core.casefile import save_case
from viha.core.diff import diff_summary
from viha.core.edges import build_edges
from viha.core.exifutil import read_jpeg_exif
from viha.core.expand import seed_from_fact
from viha.core.identity import corroborate_identity
from viha.core.models import Case, Fact, Seed, Source, utc_now
from viha.core.people_html import facts_from_people_html
from viha.core.recipes import reverse_image_links
from viha.export.case_md import render_markdown
from viha.export.graphml import render_graphml
from viha.gui.settings_dialog import SettingsDialog
from viha.gui.views.persona import PersonaView
from viha.gui.worker import HarvestWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_short__} — {__app_name__}")
        self.resize(1360, 860)
        self.case: Case | None = None
        self.prior: Case | None = None
        self.worker: HarvestWorker | None = None
        self._selected_fact: Fact | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(10)
        layout.addWidget(self._header())

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._rail())
        split.addWidget(self._workspace())
        split.addWidget(self._detail())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([300, 740, 300])
        layout.addWidget(split, 1)

        bar = QStatusBar()
        bar.showMessage(f"{__app_short__} {__version__}  ·  public sources only")
        self.setStatusBar(bar)

    def _header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Header")
        row = QHBoxLayout(frame)
        brand = QLabel(__app_short__)
        brand.setObjectName("Brand")
        sub = QLabel("VINDICTIVE HARVEST  ·  PUBLIC-SOURCE PERSONA WORKBENCH")
        sub.setObjectName("SubBrand")
        row.addWidget(brand)
        row.addWidget(sub)
        row.addStretch()
        for label, slot in (
            ("SETTINGS", self._settings),
            ("IMAGE / EXIF", self._load_image),
            ("IMPORT PEOPLE HTML", self._import_people_html),
            ("EXPORT MD", self._export_md),
            ("EXPORT GRAPHML", self._export_graphml),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        return frame

    def _rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("Rail")
        rail.setMinimumWidth(260)
        col = QVBoxLayout(rail)

        title = QLabel("SEEDS")
        title.setObjectName("Section")
        col.addWidget(title)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Full name")
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Phone")
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.city = QLineEdit()
        self.city.setPlaceholderText("City (optional)")
        self.state = QLineEdit()
        self.state.setPlaceholderText("State (TX, etc.)")
        self.org = QLineEdit()
        self.org.setPlaceholderText("Company / org / domain")
        self.username = QLineEdit()
        self.username.setPlaceholderText('Known usernames — comma-separated; quote names with spaces, e.g. "rm -rf /my/brain"')
        for w in (self.name, self.phone, self.email, self.city, self.state, self.org, self.username):
            col.addWidget(w)

        col.addSpacing(8)
        dbs = QLabel("DATABASES")
        dbs.setObjectName("Section")
        col.addWidget(dbs)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_l = QVBoxLayout(inner)
        inner_l.setContentsMargins(0, 0, 0, 0)
        self.checks: dict[str, QCheckBox] = {}
        for collector in COLLECTORS:
            box = QCheckBox(collector.label)
            box.setChecked(collector.default_on)
            box.setToolTip(f"{collector.id}\n{collector.blurb}")
            self.checks[collector.id] = box
            inner_l.addWidget(box)
        inner_l.addStretch()
        scroll.setWidget(inner)
        col.addWidget(scroll, 1)

        self.reap_btn = QPushButton("REAP →")
        self.reap_btn.setObjectName("Reap")
        self.reap_btn.clicked.connect(self._start_reap)
        col.addWidget(self.reap_btn)
        return rail

    def _workspace(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.persona = PersonaView()
        self.persona.bind_select(self._show_fact)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Case notes (saved with the .viha file).")
        self.notes.textChanged.connect(self._persist_notes)
        self.tabs.addTab(self.persona, "PERSONA")
        self.tabs.addTab(self.notes, "NOTES")
        self.tabs.addTab(self.log, "LOG")
        return self.tabs

    def _detail(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("Detail")
        pane.setMinimumWidth(250)
        col = QVBoxLayout(pane)
        title = QLabel("DOSSIER")
        title.setObjectName("Section")
        col.addWidget(title)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Select a fact to inspect source, URL, and raw excerpt.")
        col.addWidget(self.detail, 1)
        self.open_btn = QPushButton("OPEN SOURCE")
        self.open_btn.clicked.connect(self._open_source)
        self.expand_btn = QPushButton("EXPAND FROM FACT")
        self.expand_btn.clicked.connect(self._expand_fact)
        self.rev_btn = QPushButton("REVERSE IMAGE LINKS")
        self.rev_btn.clicked.connect(self._reverse_image)
        col.addWidget(self.open_btn)
        col.addWidget(self.expand_btn)
        col.addWidget(self.rev_btn)
        return pane

    def _seed(self) -> Seed:
        return Seed(
            full_name=self.name.text(),
            phone=self.phone.text(),
            email=self.email.text(),
            city=self.city.text(),
            state=self.state.text(),
            org=self.org.text(),
            username=self.username.text(),
        )

    def _selected_ids(self) -> list[str]:
        return [cid for cid, box in self.checks.items() if box.isChecked()]

    def _start_reap(self) -> None:
        seed = self._seed()
        if seed.is_empty():
            QMessageBox.information(self, __app_short__, "Enter a name, phone, email, or org first.")
            return
        self.prior = self.case
        self._run_harvest(seed, into=None)

    def _run_harvest(self, seed: Seed, into: Case | None) -> None:
        self.log.clear()
        self.reap_btn.setEnabled(False)
        self.expand_btn.setEnabled(False)
        self.statusBar().showMessage("Reaping public sources…")
        self.worker = HarvestWorker(seed, self._selected_ids(), into=into)
        self.worker.log_line.connect(self._append_log)
        self.worker.finished_case.connect(self._on_case)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    def _append_log(self, line: str) -> None:
        self.log.appendPlainText(line)

    def _on_case(self, case: Case) -> None:
        if self.case and self.case.notes:
            case.notes = self.notes.toPlainText()
        self.case = case
        save_case(case)
        self.persona.render(case)
        self.notes.blockSignals(True)
        self.notes.setPlainText(case.notes)
        self.notes.blockSignals(False)
        self.reap_btn.setEnabled(True)
        self.expand_btn.setEnabled(True)
        self.tabs.setCurrentWidget(self.persona)
        extra = diff_summary(case, self.prior) if self.prior else ""
        self.statusBar().showMessage(
            f"{len(case.facts)} facts  ·  {len(case.candidates())} candidates  ·  "
            f"{len(case.edges)} edges  ·  {extra}  ·  {case.id}"
        )

    def _on_fail(self, err: str) -> None:
        self.reap_btn.setEnabled(True)
        self.expand_btn.setEnabled(True)
        self.statusBar().showMessage("Harvest failed")
        QMessageBox.warning(self, __app_short__, err)

    def _show_fact(self, fact: Fact) -> None:
        self._selected_fact = fact
        extra_sources = fact.extra.get("sources") or []
        extra_lines = "\n".join(
            f"  + {s.get('publisher')} {s.get('url')}" for s in extra_sources if isinstance(s, dict)
        )
        self.detail.setPlainText(
            "\n".join(
                [
                    f"FIELD     {fact.predicate}",
                    f"VALUE     {fact.value}",
                    f"SECTION   {fact.section}",
                    f"CONF      {fact.confidence:.2f}",
                    f"CANDIDATE {fact.candidate}",
                    f"HASH      {fact.extra.get('sha256_16', '—')}",
                    "",
                    f"SOURCE    {fact.source.publisher}",
                    f"URL       {fact.source.url}",
                    f"WHEN      {fact.source.retrieved_at}",
                    f"COLLECTOR {fact.source.collector}",
                    extra_lines,
                    "",
                    "RAW",
                    fact.raw or "—",
                ]
            )
        )

    def _open_source(self) -> None:
        if not self._selected_fact:
            return
        url = self._selected_fact.source.url
        if url.startswith("http"):
            QDesktopServices.openUrl(QUrl(url))

    def _expand_fact(self) -> None:
        if not self.case or not self._selected_fact:
            QMessageBox.information(self, __app_short__, "Select a fact first.")
            return
        seed = seed_from_fact(self._seed(), self._selected_fact)
        self.name.setText(seed.full_name)
        self.phone.setText(seed.phone)
        self.email.setText(seed.email)
        self.org.setText(seed.org)
        self.username.setText(seed.username)
        self.prior = Case.from_dict(self.case.to_dict())
        self._run_harvest(seed, into=self.case)

    def _reverse_image(self) -> None:
        if not self._selected_fact:
            return
        url = self._selected_fact.source.url
        if self._selected_fact.predicate == "photo":
            url = self._selected_fact.value
        if not url.startswith("http"):
            QMessageBox.information(self, __app_short__, "This fact has no image URL.")
            return
        lines = [f"{name}\n{link}" for name, link in reverse_image_links(url)]
        self.detail.appendPlainText("\n\nREVERSE IMAGE\n" + "\n\n".join(lines))
        QDesktopServices.openUrl(QUrl(reverse_image_links(url)[0][1]))

    def _load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "JPEG for EXIF", str(Path.home()), "JPEG (*.jpg *.jpeg)")
        if not path:
            return
        meta = read_jpeg_exif(Path(path))
        if not self.case:
            self.case = Case(title="Image harvest", seed=self._seed())
        src = Source(publisher="Local JPEG", url=Path(path).as_uri(), retrieved_at=utc_now(), collector="viha.exif")
        if meta.get("gps"):
            self.case.add_fact(
                Fact(predicate="gps", value=str(meta["gps"]), section="identity", confidence=0.9, source=src, extra=meta)
            )
        if meta.get("datetime"):
            self.case.add_fact(
                Fact(predicate="photo_time", value=str(meta["datetime"]), section="identity", confidence=0.8, source=src)
            )
        if meta.get("camera_model"):
            self.case.add_fact(
                Fact(
                    predicate="camera",
                    value=f"{meta.get('camera_make', '')} {meta['camera_model']}".strip(),
                    section="identity",
                    confidence=0.7,
                    source=src,
                )
            )
        self.case.add_fact(
            Fact(predicate="photo", value=path, section="identity", confidence=1.0, source=src, raw=str(meta))
        )
        self.persona.render(self.case)
        self.detail.setPlainText("EXIF\n" + "\n".join(f"{k}: {v}" for k, v in meta.items()))
        self.statusBar().showMessage(f"EXIF loaded from {path}")

    def _import_people_html(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Saved people-index HTML",
            str(Path.home()),
            "HTML (*.html *.htm);;All files (*.*)",
        )
        if not path:
            return
        html = Path(path).read_text(encoding="utf-8", errors="replace")
        seed = self._seed()
        if seed.is_empty() and not self.case:
            QMessageBox.information(self, __app_short__, "Enter a name or phone so the page can be matched.")
            return
        if self.case:
            seed = Seed(
                full_name=seed.full_name or self.case.seed.full_name,
                phone=seed.phone or self.case.seed.phone,
                email=seed.email or self.case.seed.email,
                city=seed.city or self.case.seed.city,
                state=seed.state or self.case.seed.state,
                org=seed.org or self.case.seed.org,
                username=seed.username or self.case.seed.username,
            )
        facts = facts_from_people_html(
            html,
            seed,
            collector="viha.db.people",
            imported=True,
        )
        if not facts:
            QMessageBox.information(
                self,
                __app_short__,
                "No matching name/phone facts on that page. Check the seed name matches the listing.",
            )
            return
        if not self.case:
            self.case = Case(title=f"Harvest — {seed.display_name()}", seed=seed)
        for fact in facts:
            self.case.add_fact(fact)
        corroborate_identity(self.case)
        build_edges(self.case)
        save_case(self.case)
        self.persona.render(self.case)
        self.log.appendPlainText(f"Imported {len(facts)} facts from {path}")
        self.tabs.setCurrentWidget(self.persona)
        self.statusBar().showMessage(f"Imported {len(facts)} people-index facts")

    def _persist_notes(self) -> None:
        if self.case:
            self.case.notes = self.notes.toPlainText()

    def _settings(self) -> None:
        SettingsDialog(self).exec()

    def _export_md(self) -> None:
        if not self.case:
            QMessageBox.information(self, __app_short__, "Reap a persona first.")
            return
        self.case.notes = self.notes.toPlainText()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export dossier", str(Path.home() / f"{self.case.id}.md"), "Markdown (*.md)"
        )
        if path:
            Path(path).write_text(render_markdown(self.case), encoding="utf-8")
            self.statusBar().showMessage(f"Exported {path}")

    def _export_graphml(self) -> None:
        if not self.case:
            QMessageBox.information(self, __app_short__, "Reap a persona first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export graph", str(Path.home() / f"{self.case.id}.graphml"), "GraphML (*.graphml)"
        )
        if path:
            Path(path).write_text(render_graphml(self.case), encoding="utf-8")
            self.statusBar().showMessage(f"Exported {path}")
