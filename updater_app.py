import sys
import time
import shutil
import subprocess
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox


def show_error(msg: str):
    app = QApplication([])
    QMessageBox.critical(None, "Error de actualización", msg)
    sys.exit(1)


def main():
    """
    Args esperados:
    1 = path exe actual
    2 = path exe nuevo
    3 = nueva versión
    """
    if len(sys.argv) < 4:
        show_error("Parámetros de actualización inválidos.")

    current_exe = Path(sys.argv[1])
    new_exe = Path(sys.argv[2])
    new_version = sys.argv[3]

    appdata = Path.home() / "AppData" / "Local" / "GussoniApp"
    version_file = appdata / "version.json"

    # 1. Esperar que la app principal se cierre
    time.sleep(2)

    # 2. Reemplazar exe
    try:
        shutil.copy2(new_exe, current_exe)
    except Exception as e:
        show_error(f"No se pudo reemplazar la aplicación:\n{e}")

    # 3. Escribir version.json
    try:
        version_file.write_text(
            json.dumps({"version": new_version}, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        show_error(f"No se pudo actualizar la versión:\n{e}")

    # 4. Relanzar app
    try:
        subprocess.Popen([str(current_exe)], close_fds=True)
    except Exception as e:
        show_error(f"No se pudo reiniciar la aplicación:\n{e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
