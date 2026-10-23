import asyncio

from sqlalchemy import text

from app.database.database import engine


async def test_connection():
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT version()")
        )

        print(result.scalar())


if __name__ == "__main__":
    asyncio.run(test_connection())