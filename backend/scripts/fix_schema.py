import asyncio
from sqlalchemy import text
from app.database import engine

async def fix_schema():
    print("[..] Attempting to add missing columns to scheduled_reports...")
    async with engine.begin() as conn:
        try:
            # Check if column exists (Postgres specific)
            res = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='scheduled_reports' AND column_name='frequency';
            """))
            if not res.fetchone():
                print("[!] Column 'frequency' missing. Adding now...")
                await conn.execute(text("ALTER TABLE scheduled_reports ADD COLUMN frequency VARCHAR(20) DEFAULT 'monthly';"))
                print("[OK] Column 'frequency' added.")
            else:
                print("[OK] Column 'frequency' already exists.")
            
            # Also check 'recipients' just in case
            res = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='scheduled_reports' AND column_name='recipients';
            """))
            if not res.fetchone():
                print("[!] Column 'recipients' missing. Adding now...")
                await conn.execute(text("ALTER TABLE scheduled_reports ADD COLUMN recipients JSONB DEFAULT '[]';"))
                print("[OK] Column 'recipients' added.")
                
        except Exception as e:
            print(f"[ERROR] Failed to fix schema: {e}")

if __name__ == "__main__":
    asyncio.run(fix_schema())
