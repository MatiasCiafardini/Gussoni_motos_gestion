import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from app.ui.splash import SplashScreen
from app.ui.main import start_app as start_main_app


if __name__ == "__main__":
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()

    def run_startup():
        splash.run_tasks()
        splash.finish(None)
        start_main_app(app)

    # 🔥 CLAVE: correr después de que arranca el event loop
    QTimer.singleShot(2000, run_startup)

    sys.exit(app.exec())
