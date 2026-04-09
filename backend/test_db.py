import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def test_conn():
    url = os.getenv("DATABASE_URL")
    print(f"Testing connection to: {url}")
    try:
        engine = create_async_engine(url)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            row = result.fetchone()
            print(f"SUCCESS! Database version: {row[0]}")
        await engine.dispose()
    except Exception as e:
        print(f"FAILED! Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_conn())
