from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSlider, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication
from app.ui.theme import apply_theme


class ConfiguracionGeneralPage(QWidget):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("ConfiguracionGeneralPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(16)

        # ---- Título ----
        title = QLabel("Configuración General")
        title.setStyleSheet("font-weight: 800; font-size: 1.4em;")
        root.addWidget(title)

        subtitle = QLabel("Preferencias visuales y de comportamiento del sistema.")
        subtitle.setStyleSheet("color: #6B7280;")
        root.addWidget(subtitle)

        # ---- Card Apariencia ----
        card = QFrame()
        card.setObjectName("Panel")
        card.setMaximumWidth(520)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)

        section = QLabel("Apariencia")
        section.setStyleSheet("font-weight: 700;")
        card_layout.addWidget(section)

        hint = QLabel("Ajustá cómo se ve el sistema en pantalla.")
        hint.setStyleSheet("color: #6B7280;")
        card_layout.addWidget(hint)

        # ---- Fila tamaño texto ----
        row = QHBoxLayout()

        lbl = QLabel("Tamaño del texto")
        lbl.setStyleSheet("font-weight: 500;")
        row.addWidget(lbl)

        row.addStretch(1)

        self.value_lbl = QLabel()
        self.value_lbl.setStyleSheet("color: #6B7280;")
        row.addWidget(self.value_lbl)

        card_layout.addLayout(row)

        # ---- Slider ----
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(90)
        self.slider.setMaximum(150)
        self.slider.setSingleStep(5)
        self.slider.setPageStep(10)
        card_layout.addWidget(self.slider)

        foot = QLabel("Los cambios se aplican al instante.")
        foot.setStyleSheet("color: #9CA3AF; font-size: 0.9em;")
        card_layout.addWidget(foot)

        root.addWidget(card)
        root.addStretch(1)

        # ---- Settings ----
        self.settings = QSettings("Gussoni", "GussoniApp")
        scale = self.settings.value("ui/font_scale", 1.0, float)

        self.slider.setValue(int(scale * 100))
        self._update_label(self.slider.value())

        self.slider.valueChanged.connect(self._on_scale_changed)

    def _update_label(self, value: int):
        self.value_lbl.setText(f"{value} %")

    def _on_scale_changed(self, value: int):
        scale = value / 100
        self._update_label(value)

        self.settings.setValue("ui/font_scale", scale)
        apply_theme(QApplication.instance(), base_font_pt=11, scale=scale)
