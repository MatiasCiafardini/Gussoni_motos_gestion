from __future__ import annotations

import json
from pathlib import Path
import os
from app.shared.paths import user_data_path

CONFIG_FILENAME = "config.json"


def config_path() -> Path:
    return Path(user_data_path()) / CONFIG_FILENAME


def ensure_config_exists() -> Path:
    # 🔑 definir EXPLÍCITAMENTE el directorio de config
    base_dir = Path(os.getenv("APPDATA")) / "GussoniApp"
    base_dir.mkdir(parents=True, exist_ok=True)

    path = base_dir / "config.json"

    if not path.exists():
        default_config = {
            "db": {
                "host": "",
                "port": 3306,
                "user": "",
                "password": "",
                "name": "",
                "pool_size": 5,
                "pool_timeout": 30
            },
            "arca": {
                "cuit": "33717057479",
                "modo": "PRODUCCION",
                "cert_path": "certificados/prod.crt",
                "key_path": "certificados/prod.key",
                "key_password": ""
            },
            "arca_homo": {
                "cuit": "20240620988",
                "modo": "HOMOLOGACION",
                "cert_path": "certificados/homo.crt",
                "key_path": "certificados/homo.key",
                "key_password": "crisgus1974"
            }
        }

        path.write_text(
            json.dumps(default_config, indent=4),
            encoding="utf-8"
        )

    return path

def db_config_completa(config: dict) -> bool:
    db = config.get("db", {})
    return all([
        db.get("host"),
        db.get("user"),
        db.get("name"),
    ])



def config_path() -> Path:
    """
    Ruta al archivo de configuración principal.
    Usa AppData\\Roaming\\GussoniApp\\config.json
    """
    return Path(user_data_path()) / "config.json"


def save_config(config: dict) -> None:
    """
    Guarda el config.json en AppData.
    Asegura que la carpeta exista.
    """
    path = config_path()

    # 🔑 asegurar carpeta
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(config, indent=4),
        encoding="utf-8"
    )

def load_config() -> dict:
    path = ensure_config_exists()
    return json.loads(path.read_text(encoding="utf-8"))
