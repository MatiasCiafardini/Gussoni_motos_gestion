from __future__ import annotations

import json
from pathlib import Path

from app.shared.paths import user_data_path

CONFIG_FILENAME = "config.json"


def config_path() -> Path:
    return Path(user_data_path()) / CONFIG_FILENAME


def ensure_config_exists() -> Path:
    path = config_path()

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


def load_config() -> dict:
    path = ensure_config_exists()
    return json.loads(path.read_text(encoding="utf-8"))
