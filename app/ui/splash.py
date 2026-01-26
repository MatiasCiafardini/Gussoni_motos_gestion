from PySide6.QtWidgets import QSplashScreen
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer

from app.ui.utils.resources import resource_path
from app.core.updater import check_for_update
import app.ui.utils.paths as paths

class SplashScreen(QSplashScreen):
    def __init__(self):
        pixmap = QPixmap(str(paths.LOGO_GUSSONI))
        pixmap = pixmap.scaled(
            300, 180,                 # 👈 tamaño del logo
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation   # 👈 se ve nítido
        )
        super().__init__(pixmap)

        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.showMessage(
            "Iniciando Gussoni App...",
            Qt.AlignBottom | Qt.AlignCenter,
            Qt.white
        )

    def run_tasks(self):
        """
        Acá va TODO lo que hoy está en run.py
        y lo pesado que no querés en main()
        """
        try:
            self.showMessage(
                "Buscando actualizaciones...",
                Qt.AlignBottom | Qt.AlignCenter,
                Qt.white
            )
            update = check_for_update()
            if update:
                print("Hay una actualización disponible:", update["version"])
            else:
                print("La aplicación está actualizada")
        except Exception as e:
            print("Error al buscar actualizaciones:", e)
