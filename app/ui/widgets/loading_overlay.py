from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame


class _Spinner(QWidget):
    """
    Spinner circular animado (sin GIF) — gira constantemente.
    Dibujado con QPainter.
    """
    def __init__(self, parent=None, radius: int = 12, line_width: int = 3, speed_ms: int = 0):
        super().__init__(parent)
        self._angle = 0.0
        self._radius = radius
        self._line_width = line_width
        self._color = QColor(255, 255, 255)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._timer.start(speed_ms)  # 60 FPS aprox
        self.setFixedSize(radius * 2 + 8, radius * 2 + 8)

    def _on_timeout(self):
        # Incrementar ángulo y forzar repintado
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)

        pen = QPen(self._color)
        pen.setWidth(self._line_width)
        painter.setPen(pen)

        # 12 líneas con opacidad decreciente (efecto rueda)
        for i in range(12):
            alpha = int(255 * (i + 1) / 12)
            pen.setColor(QColor(self._color.red(), self._color.green(), self._color.blue(), alpha))
            painter.setPen(pen)
            painter.drawLine(0, -self._radius + 2, 0, -self._radius + 8)
            painter.rotate(30)
        painter.end()


class LoadingOverlay(QWidget):
    """
    Overlay liviano y elegante con spinner animado y texto.
    No bloquea ni oscurece la interfaz.
    """

    def __init__(self, parent=None, text: str = "Procesando..."):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowFlags(Qt.SubWindow)
        self.setVisible(False)

        # === Panel flotante ===
        self.panel = QFrame(self)
        self.panel.setObjectName("LoadingPanel")
        self.panel.setStyleSheet("""
            QFrame#LoadingPanel {
                background-color: rgba(40, 40, 40, 180);
                color: white;
                border-radius: 10px;
                padding: 18px 30px;
            }
            QLabel { color: white; }
        """)

        layout = QVBoxLayout(self.panel)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(20, 12, 20, 12)

        # Spinner
        self.spinner = _Spinner(self.panel, radius=12, line_width=3, speed_ms=16)

        # Texto
        self.lbl_text = QLabel(text)
        self.lbl_text.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.lbl_text.setFont(font)

        layout.addWidget(self.spinner, alignment=Qt.AlignCenter)
        layout.addWidget(self.lbl_text, alignment=Qt.AlignCenter)

        self._centered = False

    def paintEvent(self, event):
        # Fondo completamente transparente
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.end()

    def resizeEvent(self, event):
        """Recentrar automáticamente cuando el padre cambia tamaño."""
        super().resizeEvent(event)
        self._recenter_panel()

    def _recenter_panel(self):
        """Centrar el panel en el contenedor actual."""
        if not self.parent():
            return
        pw, ph = self.width(), self.height()
        panel_w, panel_h = self.panel.sizeHint().width(), self.panel.sizeHint().height()
        self.panel.setGeometry(
            (pw - panel_w) // 2,
            (ph - panel_h) // 2,
            panel_w,
            panel_h
        )

    def show_overlay(self):
        if not self.parent():
            return
        self.setGeometry(self.parent().rect())
        self._recenter_panel()
        self.panel.show()
        self.raise_()
        self.setVisible(True)

    def hide_overlay(self):
        self.setVisible(False)
