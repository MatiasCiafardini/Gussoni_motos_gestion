from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path

# === Localizar el archivo .env ===
# Estructura:
# APP_GUSSONI/
#   .env           <-- acá
#   app/
#     core/
#       config.py  <-- estamos acá
#
# Entonces: core -> app -> APP_GUSSONI  => parent.parent.parent
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# Cargar variables del .env si existe
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    print("[DEBUG] .env NO encontrado en esa ruta, no se cargó nada")

def _db(name: str, default: str = "") -> str:
    """
    Busca primero APP_DB_<NAME>, si no existe busca DB_<NAME>,
    si tampoco existe devuelve el default.
    """
    return os.getenv(f"APP_DB_{name}") or os.getenv(f"DB_{name}", default)

@dataclass(frozen=True)
class Settings:
    DB_HOST: str = _db("HOST", "")
    DB_PORT: int = int(_db("PORT", ""))
    DB_USER: str = _db("USER", "")
    DB_PASSWORD: str = _db("PASSWORD", "")
    DB_NAME: str = _db("NAME", "")

    DB_SSL_CA: str = _db("SSL_CA", "")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", ""))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", ""))

    APP_NAME: str = "MotoAgency Desk"

settings = Settings()