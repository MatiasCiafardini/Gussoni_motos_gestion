# app/utils/paths.py
import sys
from pathlib import Path


def base_dir() -> Path:
    # PyInstaller (exe)
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)

    # Desarrollo normal
    return Path(__file__).resolve().parents[2]


BASE_DIR = base_dir()

# Rutas principales
ASSETS_DIR = BASE_DIR / "assets"

# Archivos concretos
LOGO_GUSSONI = ASSETS_DIR / "logo.png"
LOGO_AFIP   = ASSETS_DIR / "logo_arca.jpg"
APP_ICON    = ASSETS_DIR / "logo.ico"
FIRMA_ADMIN = ASSETS_DIR / "firma.png"
