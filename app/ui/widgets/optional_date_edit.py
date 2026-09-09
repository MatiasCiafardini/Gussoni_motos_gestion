from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QAbstractSpinBox, QDateEdit


class OptionalDateEdit(QDateEdit):
    """Editor de fecha que admite un valor vacio (sin limite)."""

    NULL_DATE = QDate(1900, 1, 1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDisplayFormat("dd/MM/yyyy")
        self.setCalendarPopup(True)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setMinimumDate(self.NULL_DATE)
        self.setMaximumDate(QDate(7999, 12, 31))
        self.setSpecialValueText("Sin límite")
        self.setToolTip("Delete o Backspace para quitar este limite de fecha")
        self.lineEdit().setClearButtonEnabled(True)
        self.lineEdit().textEdited.connect(self._on_text_edited)

    def clear(self) -> None:
        self.setDate(self.NULL_DATE)

    def optional_date(self) -> Optional[QDate]:
        value = self.date()
        return None if value == self.NULL_DATE else value

    def _on_text_edited(self, text: str) -> None:
        if not text.strip():
            self.clear()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.clear()
            event.accept()
            return
        super().keyPressEvent(event)
