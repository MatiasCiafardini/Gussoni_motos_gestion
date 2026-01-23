import json
import requests
import sys
import os

UPDATE_URL = "https://raw.githubusercontent.com/MatiasCiafardini/Gussoni_motos_gestion/main/version.json"


def resource_path(rel_path: str) -> str:
    """
    Devuelve el path correcto tanto en desarrollo como dentro del exe
    """
    base = getattr(sys, "_MEIPASS", os.getcwd())
    return os.path.join(base, rel_path)


def get_local_version() -> str:
    """
    Lee la versión local desde version.json (empaquetado en el exe)
    """
    path = resource_path("version.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["version"]


def check_for_update():
    """
    Compara versión local vs remota.
    Devuelve dict con info del update o None.
    """
    local_version = get_local_version()

    r = requests.get(UPDATE_URL, timeout=5)
    r.raise_for_status()
    remote = r.json()

    if remote.get("version") != local_version:
        return remote

    return None
