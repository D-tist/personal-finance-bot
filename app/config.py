import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "finance")
POSTGRES_USER = os.getenv("POSTGRES_USER", "finance_user")
POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
    "finance_password",
)


DATABASE_URL = (
    "postgresql+asyncpg://"
    f"{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не указан в файле .env"
    )