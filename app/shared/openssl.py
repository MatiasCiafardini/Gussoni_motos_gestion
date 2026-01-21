from __future__ import annotations

import sys
from pathlib import Path


def get_openssl_path() -> Path:
    """
    Devuelve el path absoluto a openssl.exe embebido en la app.
    Funciona en desarrollo y en PyInstaller.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller
        base_dir = Path(sys._MEIPASS)
        openssl_path = base_dir / "app" / "tools" / "openssl" / "openssl.exe"
    else:
        # Desarrollo (app/ está dos niveles arriba de este archivo)
        base_dir = Path(__file__).resolve().parents[2]
        openssl_path = base_dir / "app" / "tools" / "openssl" / "openssl.exe"

    if not openssl_path.exists():
        raise FileNotFoundError(f"OpenSSL no encontrado en: {openssl_path}")

    return openssl_path
