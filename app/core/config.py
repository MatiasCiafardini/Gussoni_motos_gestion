from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _db(name: str, default: str = "") -> str:
    # Prioriza APP_DB_* y cae a DB_*
    return os.getenv(f"APP_DB_{name}") or os.getenv(f"DB_{name}", default)

@dataclass(frozen=True)
class Settings:
    DB_HOST: str = _db("HOST", "34.176.19.140")
    DB_PORT: int = int(_db("PORT", "3306"))
    DB_USER: str = _db("USER", "matiasciafardini")
    DB_PASSWORD: str = _db("PASS", "Jackymat32.")
    DB_NAME: str = _db("NAME", "motoagency")

    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    APP_NAME: str = "MotoAgency Desk"

settings = Settings()
