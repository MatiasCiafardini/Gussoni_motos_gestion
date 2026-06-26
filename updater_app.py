import sys
import time
import shutil
import subprocess
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QProgressBar 
from PySide6.QtCore import Qt, QTimer
import app.ui.app_message as popUp


def show_error(msg: str):
    popUp.toast(None, "Error de actualización", kind="error")
    sys.exit(1)

def create_updater_window():
    window = QWidget()
    window.setWindowTitle("Gussoni App")
    window.setFixedSize(380, 160)
    window.setWindowFlags(
        Qt.Window |
        Qt.CustomizeWindowHint |
        Qt.WindowMinimizeButtonHint
    )

    layout = QVBoxLayout(window)

    title = QLabel("Actualizando Gussoni App")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size: 15px; font-weight: bold;")

    status = QLabel("Preparando actualización…")
    status.setAlignment(Qt.AlignCenter)

    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setTextVisible(True)

    layout.addWidget(title)
    layout.addWidget(status)
    layout.addWidget(progress)

    window.show()

    return window, status, progress
def start_fake_progress(progress: QProgressBar, status: QLabel) -> QTimer:
    steps = [
        (10, "Preparando actualización…"),
        (30, "Cerrando aplicación anterior…"),
        (60, "Reemplazando archivos…"),
        (85, "Actualizando versión…"),
        (100, "Finalizando…"),
    ]

    step_index = 0

    def advance():
        nonlocal step_index
        if step_index >= len(steps):
            return

        value, text = steps[step_index]
        progress.setValue(value)
        status.setText(text)
        step_index += 1

    timer = QTimer(status)
    timer.timeout.connect(advance)
    timer.start(600)  # cada 600 ms
    return timer


def main() -> int:
    app = QApplication(sys.argv)

    if len(sys.argv) < 4:
        popUp.critical(None, "Error", "Parámetros inválidos")
        return 1

    window, status, progress = create_updater_window()
    timer = start_fake_progress(progress, status)
    app.processEvents()

    current_exe = Path(sys.argv[1])
    new_exe = Path(sys.argv[2])
    new_version = sys.argv[3]

    appdata = Path.home() / "AppData" / "Local" / "GussoniApp"
    version_file = appdata / "version.json"

    time.sleep(2)

    try:
        backup_exe = current_exe.with_suffix(".old")

        # eliminar backup previo si existe
        if backup_exe.exists():
            backup_exe.unlink()

        # renombrar exe actual (libera el lock)
        current_exe.rename(backup_exe)

        # mover el nuevo exe al lugar correcto
        shutil.move(new_exe, current_exe)

        progress.setValue(70)
        status.setText("Actualizando versión…")

        version_file.write_text(
            json.dumps({"version": new_version}, indent=2),
            encoding="utf-8"
        )

        progress.setValue(100)
        status.setText("Reiniciando aplicación…")

        creationflags = 0
        if sys.platform.startswith("win"):
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [str(current_exe)],
            close_fds=True,
            creationflags=creationflags,
        )
    except Exception as e:
        popUp.critical(None, "Error de actualización", str(e))
        if timer.isActive():
            timer.stop()
        window.close()
        app.processEvents()
        app.quit()
        return 1

    if timer.isActive():
        timer.stop()
    window.close()
    window.deleteLater()
    app.processEvents()
    app.quit()
    return 0




if __name__ == "__main__":
    sys.exit(main())
