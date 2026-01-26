import json
import requests
import sys
import os
from pathlib import Path

from packaging.version import Version
UPDATE_URL = "https://raw.githubusercontent.com/MatiasCiafardini/Gussoni_motos_gestion/main/version.json"


def get_app_data_dir() -> Path:
    """
    Directorio persistente de la app (fuera del exe)
    """
    return Path.home() / "AppData" / "Local" / "GussoniApp"


def get_version_file() -> Path:
    """
    Ruta persistente de version.json
    """
    app_dir = get_app_data_dir()
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "version.json"


def resource_path(rel_path: str) -> str:
    """
    Devuelve el path correcto tanto en desarrollo como dentro del exe
    """
    base = getattr(sys, "_MEIPASS", os.getcwd())
    return os.path.join(base, rel_path)


def get_local_version() -> str:
    version_file = get_version_file()

    if not version_file.exists():
        version_file.write_text(
            json.dumps({"version": "1.0.0"}, indent=2),
            encoding="utf-8"
        )

    with open(version_file, "r", encoding="utf-8") as f:
        return json.load(f)["version"]

def normalize(v) -> str:
    return str(v).strip()

def check_for_update():
    local_version = normalize(get_local_version())
    

    
    
    r = requests.get(UPDATE_URL, timeout=5)
    r.raise_for_status()
    remote = r.json()
    
    remote_version = normalize(remote.get("version"))
    if Version(remote_version) > Version(local_version):
        return remote

    return None

