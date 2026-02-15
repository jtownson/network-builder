from app.core.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


def db_conninfo() -> str:
    return (
        f"host={DB_HOST} "
        f"port={DB_PORT} "
        f"dbname={DB_NAME} "
        f"user={DB_USER} "
        f"password={DB_PASSWORD}"
    )
