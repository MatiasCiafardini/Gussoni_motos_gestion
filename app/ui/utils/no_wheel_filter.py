from PySide6.QtCore import QObject, QEvent

class NoWheelFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            event.ignore()
            return True
        return False
