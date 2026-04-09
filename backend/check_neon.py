import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def check_data():
    url = os.getenv("DATABASE_URL").replace("?sslmode=require", "")
    engine = create_async_engine(url, connect_args={"ssl": True})
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id, name, company FROM datasets;"))
        rows = result.fetchall()
        print("DATASETS IN NEON:")
        for r in rows:
            print(f"ID: {r[0]}, Name: {r[1]}, Company: {r[2]}")
            
        result = await conn.execute(text("SELECT count(*) FROM transactions;"))
        count = result.scalar()
        print(f"TOTAL TRANSACTIONS: {count}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_data())
