from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings
from loguru import logger


def _mysql_url() -> str:
    # Using mysql+mysqlconnector
    return (
        f"mysql+mysqlconnector://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        f"?charset=utf8mb4"
    )


engine = create_engine(
    _mysql_url(),
    connect_args={
        "ssl_ca": settings.DB_SSL_CA  # <- ruta al certificado CA de Aiven
    },
    pool_size=settings.DB_POOL_SIZE,
    pool_pre_ping=True,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session():
    try:
        db = SessionLocal()
        yield db
    except SQLAlchemyError as e:
        logger.exception("Error creando sesión DB: {}", e)
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass
