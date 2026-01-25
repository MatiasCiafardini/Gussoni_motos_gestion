import pymysql
from app.core.config import settings

def probar_conexion_db(db_config: dict) -> tuple[bool, str | None]:
    try:
        conn = pymysql.connect(
            host=db_config["host"],
            port=int(db_config.get("port", 3306)),
            user=db_config["user"],
            password=db_config.get("password", ""),
            database=db_config["name"],
            connect_timeout=5,
        )
        conn.close()
        return True, None
    except Exception as e:
        return False, str(e)

