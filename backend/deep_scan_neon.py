import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def deep_scan():
    url = os.getenv("DATABASE_URL").replace("?sslmode=require", "")
    engine = create_async_engine(url, connect_args={"ssl": True})
    
    async with engine.connect() as conn:
        print("Deep scanning Neon for 'სოკარ'...")
        
        # Check all tables and text columns
        result = await conn.execute(text("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND data_type IN ('character varying', 'text');
        """))
        columns = result.fetchall()
        
        for table, col in columns:
            try:
                res = await conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE '%სოკარ%'"))
                count = res.scalar()
                if count > 0:
                    print(f"FOUND in Table: {table}, Column: {col} ({count} rows)")
                    # Show one example
                    sample = await conn.execute(text(f"SELECT {col} FROM {table} WHERE {col} LIKE '%სოკარ%' LIMIT 1"))
                    print(f"  Example: {sample.scalar()}")
            except Exception as e:
                pass
                
        print("Deep scan complete.")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(deep_scan())
