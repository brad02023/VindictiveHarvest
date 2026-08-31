from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

from viha.core.settings import load_settings, save_settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VIHA settings — free keys only")
        self.setMinimumWidth(420)
        data = load_settings()
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "Optional free credentials. Paid products (HIBP, Shodan paid, "
                "OpenCorporates token, people-search licenses) are not used."
            )
        )
        form = QFormLayout()
        self.github = QLineEdit(data.get("github_token", ""))
        self.github.setEchoMode(QLineEdit.EchoMode.Password)
        self.github.setPlaceholderText("ghp_… personal access token (free)")
        self.fec = QLineEdit(data.get("fec_api_key", "DEMO_KEY"))
        self.fec.setPlaceholderText("DEMO_KEY or free key from api.open.fec.gov")
        form.addRow("GitHub token", self.github)
        form.addRow("FEC API key", self.fec)
        lay.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _save(self) -> None:
        save_settings({"github_token": self.github.text().strip(), "fec_api_key": self.fec.text().strip() or "DEMO_KEY"})
        self.accept()
