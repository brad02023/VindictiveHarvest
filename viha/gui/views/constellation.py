from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from viha.core.edges import build_edges
from viha.core.models import Case
from viha.gui.theme import AMBER, BG, BONE, GREEN, LINE, MUTED, RUST


class ConstellationView(QGraphicsView):
    node_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QBrush(QColor(BG)))
        self._labels: list[str] = []

    def render(self, case: Case) -> None:
        scene = QGraphicsScene(self)
        scene.setBackgroundBrush(QBrush(QColor(BG)))
        self.setScene(scene)
        build_edges(case)
        nodes: list[tuple[str, str]] = [("persona", case.seed.display_name())]
        for fact in case.visible_facts()[:36]:
            nodes.append((fact.section, fact.value[:42]))
        self._labels = [n[1] for n in nodes]
        if len(nodes) == 1:
            self._node(scene, 0, 0, "persona", "No facts yet")
            return
        self._node(scene, 0, 0, "persona", nodes[0][1])
        ring = nodes[1:]
        radius = 190 + min(90, len(ring) * 4)
        for i, (kind, label) in enumerate(ring):
            angle = (2 * math.pi * i) / len(ring) - math.pi / 2
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            line = QGraphicsLineItem(0, 0, x, y)
            line.setPen(QPen(QColor(LINE), 1))
            scene.addItem(line)
            self._node(scene, x, y, kind, label)
        scene.setSceneRect(-radius - 90, -radius - 50, (radius + 90) * 2, (radius + 50) * 2)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if item and hasattr(item, "data") and item.data(0):
            self.node_clicked.emit(str(item.data(0)))

    def _node(self, scene: QGraphicsScene, x: float, y: float, kind: str, label: str) -> None:
        color = {
            "persona": AMBER,
            "social": GREEN,
            "legal": RUST,
            "contact": BONE,
            "identity": AMBER,
            "business": "#6EA8FE",
            "sanctions": RUST,
            "infra": MUTED,
            "web": MUTED,
            "recipes": MUTED,
        }.get(kind, BONE)
        r = 10 if kind == "persona" else 6
        dot = QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
        dot.setPos(QPointF(x, y))
        dot.setBrush(QBrush(QColor(color)))
        dot.setPen(QPen(Qt.PenStyle.NoPen))
        dot.setData(0, label)
        scene.addItem(dot)
        text = QGraphicsTextItem(label)
        text.setDefaultTextColor(QColor(BONE))
        text.setFont(QFont("Segoe UI", 8))
        text.setPos(x + 12, y - 10)
        text.setData(0, label)
        scene.addItem(text)
