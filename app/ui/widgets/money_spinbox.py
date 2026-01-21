from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtCore import Qt, QLocale


class MoneySpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setDecimals(2)
        self.setMinimum(0.00)
        self.setMaximum(999_999_999.99)
        self.setValue(0.00)

        self.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.setMinimumHeight(36)

        locale = QLocale(QLocale.Spanish, QLocale.Argentina)
        self.setLocale(locale)
        self.setPrefix("$ ")
        self.setGroupSeparatorShown(True)

        # No edición directa
        self.lineEdit().setReadOnly(True)

    def keyPressEvent(self, event):
        key = event.key()

        # Números
        if Qt.Key_0 <= key <= Qt.Key_9:
            digit = key - Qt.Key_0

            # valor actual en centavos
            cents = int(round(self.value() * 100))

            # desplazamiento tipo POS
            cents = cents * 10 + digit

            # límite de seguridad
            if cents > self.maximum() * 100:
                return

            self.setValue(cents / 100)
            return

        # Backspace → borrar último dígito
        if key == Qt.Key_Backspace:
            cents = int(round(self.value() * 100))
            cents = cents // 10
            self.setValue(cents / 100)
            return

        # Ignorar todo lo demás
        event.ignore()
