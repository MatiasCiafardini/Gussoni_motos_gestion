from __future__ import annotations

from loguru import logger
from pathlib import Path
import sys

from app.shared.paths import user_data_path


def setup_logging(app_name: str = "MotoAgency Desk") -> None:
    # Carpeta segura de logs (AppData)
    log_dir = Path(user_data_path()) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    # 🔹 Consola SOLO si existe (en exe windowed NO existe)
    if sys.stdout:
        logger.add(
            sys.stdout,
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>",
            backtrace=False,
            diagnose=False,
        )

    # 🔹 Archivo (siempre válido)
    logger.add(
        log_dir / f"{app_name}.log",
        rotation="1 week",
        retention="4 weeks",
        level="INFO",
        encoding="utf-8",
        backtrace=False,
        diagnose=False,
    )

    logger.info("Logging inicializado correctamente")
