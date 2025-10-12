from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

class PlaceholderPage(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        box = QFrame(self)
        box.setObjectName("MetricCard")
        layBox = QVBoxLayout(box)
        lbl = QLabel(f"<h2 style='margin:0;'> {title} </h2><p style='color:#6B7280;'>Pantalla en construcción…</p>")
        layBox.addWidget(lbl)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,16,16,16)
        lay.addWidget(box, 0, Qt.AlignTop)
