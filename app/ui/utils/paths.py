# app/utils/paths.py
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


if is_frozen():
    # 👉 Ejecutable (exe / instalado)
    BASE_DIR = Path(sys.executable).parent
else:
    # 👉 Desarrollo (repo)
    BASE_DIR = Path(__file__).resolve().parents[2]  # app/


# Rutas principales
ASSETS_DIR = BASE_DIR / "assets"

# Archivos concretos
LOGO_GUSSONI = ASSETS_DIR / "logo.png"
LOGO_AFIP   = ASSETS_DIR / "logo_arca.jpg"
APP_ICON    = ASSETS_DIR / "logo.ico"
