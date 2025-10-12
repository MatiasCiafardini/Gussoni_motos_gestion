from __future__ import annotations
from loguru import logger
import sys
from pathlib import Path

def setup_logging(app_name: str = "MotoAgency Desk") -> None:
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{message}</cyan>")
    logger.add(log_dir / "app.log", rotation="1 week", retention="4 weeks", level="INFO")
