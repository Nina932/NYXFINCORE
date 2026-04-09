import asyncio
import asyncpg
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_asyncpg")

async def test_connection():
    # Exactly what the user provided, except removing the driver if needed for asyncpg.connect
    # asyncpg.connect handles postgresql://
    url = "postgresql://neondb_owner:npg_F62INGHixRfE@ep-raspy-water-agnr9eff-pooler.c-2.eu-central-1.aws.neon.tech/neondb?sslmode=require"
    
    logger.info(f"Connecting to: {url.split('@')[-1]}")
    try:
        conn = await asyncpg.connect(url)
        logger.info("SUCCESS: Connected to Neon via asyncpg directly.")
        await conn.close()
    except Exception as e:
        logger.error(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
