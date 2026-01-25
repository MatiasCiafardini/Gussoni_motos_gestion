from app.core.config import settings

def db_config_completa() -> bool:
    return all([
        settings.DB_HOST,
        settings.DB_USER,
        settings.DB_NAME,
    ])
