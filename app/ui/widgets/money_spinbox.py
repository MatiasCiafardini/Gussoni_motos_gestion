import re

from PySide6.QtWidgets import QApplication, QDoubleSpinBox
from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QWheelEvent


class MoneySpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Configuracion basica
        self.setDecimals(2)
        self.setMinimum(0.00)
        self.setMaximum(999_999_999.99)
        self.setValue(0.00)

        # Apariencia
        self.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.setMinimumHeight(36)

        # Locale Argentina
        locale = QLocale(QLocale.Spanish, QLocale.Argentina)
        self.setLocale(locale)
        self.setPrefix("$ ")
        self.setGroupSeparatorShown(True)

        # No permitir edicion directa
        self.lineEdit().setReadOnly(True)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if (modifiers & Qt.ControlModifier and key == Qt.Key_V) or (
            modifiers & Qt.ShiftModifier and key == Qt.Key_Insert
        ):
            value = self._parse_money_text(QApplication.clipboard().text())
            if value is not None:
                self.setValue(value)
                event.accept()
                return

        # Numeros (input tipo POS)
        if Qt.Key_0 <= key <= Qt.Key_9:
            digit = key - Qt.Key_0

            # Valor actual en centavos
            cents = int(round(self.value() * 100))

            # Desplazamiento
            cents = cents * 10 + digit

            # Limite de seguridad
            if cents > int(self.maximum() * 100):
                return

            self.setValue(cents / 100)
            return

        # Backspace: borrar ultimo digito
        if key == Qt.Key_Backspace:
            cents = int(round(self.value() * 100))
            cents //= 10
            self.setValue(cents / 100)
            return

        # Ignorar todo lo demas
        event.ignore()

    def _parse_money_text(self, text: str):
        value = str(text or "").strip()
        if not value:
            return None

        value = value.replace("$", "").replace(" ", "")
        value = re.sub(r"[^0-9,.\-]", "", value)
        if not value:
            return None

        if "," in value and "." in value:
            if value.rfind(",") > value.rfind("."):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")
        elif "," in value:
            value = value.replace(".", "").replace(",", ".")

        try:
            parsed = float(value)
        except ValueError:
            return None

        if parsed < self.minimum():
            parsed = self.minimum()
        if parsed > self.maximum():
            parsed = self.maximum()
        return parsed

    # Deshabilitar scroll del mouse
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()
