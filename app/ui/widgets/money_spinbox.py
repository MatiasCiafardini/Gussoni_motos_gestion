from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtCore import Qt, QLocale
from PySide6.QtGui import QWheelEvent


class MoneySpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Configuración básica
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

        # No permitir edición directa
        self.lineEdit().setReadOnly(True)

    def keyPressEvent(self, event):
        key = event.key()

        # Números (input tipo POS)
        if Qt.Key_0 <= key <= Qt.Key_9:
            digit = key - Qt.Key_0

            # Valor actual en centavos
            cents = int(round(self.value() * 100))

            # Desplazamiento
            cents = cents * 10 + digit

            # Límite de seguridad
            if cents > int(self.maximum() * 100):
                return

            self.setValue(cents / 100)
            return

        # Backspace → borrar último dígito
        if key == Qt.Key_Backspace:
            cents = int(round(self.value() * 100))
            cents //= 10
            self.setValue(cents / 100)
            return

        # Ignorar todo lo demás
        event.ignore()

    # 🚫 Deshabilitar scroll del mouse
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()
