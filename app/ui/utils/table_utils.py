from PySide6.QtWidgets import QTableWidget, QHeaderView
from PySide6.QtCore import QSettings

def setup_compact_table(table: QTableWidget):
    """
    Configura una tabla con filas compactas y escalables
    según el font_scale del sistema.
    """
    settings = QSettings("Gussoni", "GussoniApp")
    scale = settings.value("ui/font_scale", 1.0, float)

    table.setWordWrap(False)

    vh = table.verticalHeader()
    vh.setSectionResizeMode(QHeaderView.Fixed)
    vh.setDefaultSectionSize(int(32 * (scale * 0.9)))
