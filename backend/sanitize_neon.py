import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def sanitize_neon():
    url = os.getenv("DATABASE_URL").replace("?sslmode=require", "")
    engine = create_async_engine(url, connect_args={"ssl": True})
    company_name = os.getenv("COMPANY_NAME", "NYXCoreThinker LLC")
    
    async with engine.begin() as conn:
        print(f"Sanitizing Neon database with company: {company_name}")
        
        # 1. Update all datasets to the new company name
        await conn.execute(text(
            "UPDATE datasets SET company = :name"
        ), {"name": company_name})
        
        # 2. Rename datasets that mention SOCAR
        await conn.execute(text(
            "UPDATE datasets SET name = REPLACE(name, 'SOCAR', 'NYX CoreFinLogic') WHERE name LIKE '%SOCAR%'"
        ))
        
        print("Sanitization complete.")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(sanitize_neon())
