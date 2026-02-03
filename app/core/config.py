from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from app.shared.config_loader import load_config
from app.shared.paths import user_data_path

_cfg = load_config()

_db = _cfg.get("db", {})
_arca = _cfg.get("arca", {})
_arca_homo = _cfg.get("arca_homo", {})


def _str(v, default=""):
    return v if isinstance(v, str) else default


def _int(v, default):
    try:
        return int(v)
    except Exception:
        return default


def _path(rel_path: str) -> str:
    """
    Convierte rutas relativas (certificados/xxx.crt)
    a rutas absolutas en AppData.
    """
    return str(Path(user_data_path()) / rel_path)


@dataclass(frozen=True)
class Settings:
    # ================= DB =================
    DB_HOST: str = _str(_db.get("host"))
    DB_PORT: int = _int(_db.get("port"), 3306)
    DB_USER: str = _str(_db.get("user"))
    DB_PASSWORD: str = _str(_db.get("password"))
    DB_NAME: str = _str(_db.get("name"))
    DB_POOL_SIZE: int = _int(_db.get("pool_size"), 5)
    DB_POOL_TIMEOUT: int = _int(_db.get("pool_timeout"), 30)
    DB_SSL_CA: str = _path(_str(_db.get("ssl_ca")))

    # =============== ARCA =================
    # ÚNICA bandera de entorno
    ARCA_ENV: str = _str(_arca.get("environment"), "PRODUCCION").upper() #HOMOLOGACION O PRODUCCION

    # --- Producción ---
    ARCA_PROD_CUIT: str = _str(_arca.get("cuit"))
    ARCA_PROD_CERT_PATH: str = _path(_str(_arca.get("cert_path")))
    ARCA_PROD_KEY_PATH: str = _path(_str(_arca.get("key_path")))
    ARCA_PROD_KEY_PASSWORD: str = _str(_arca.get("key_password"))

    # --- Homologación ---
    ARCA_HOMO_CUIT: str = _str(_arca_homo.get("cuit"))
    ARCA_HOMO_CERT_PATH: str = _path(_str(_arca_homo.get("cert_path")))
    ARCA_HOMO_KEY_PATH: str = _path(_str(_arca_homo.get("key_path")))
    ARCA_HOMO_KEY_PASSWORD: str = _str(_arca_homo.get("key_password"))

    # =============== APP ==================
    APP_NAME: str = "MotoAgency Desk"
    APP_DATA_DIR: str = str(user_data_path())


settings = Settings()
