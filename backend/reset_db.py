#!/usr/bin/env python
"""
FinAI Database Reset Utility
Resets the development database and reloads seed data
Usage: python reset_db.py
"""

import asyncio
import sys
from pathlib import Path
from app.database import engine, init_db, drop_db, AsyncSessionLocal
from app.services.seed_data import seed_database

async def reset_database():
    """Drop all tables and recreate with seed data."""
    try:
        print("🗑️  Dropping all tables...")
        await drop_db()
        print("✅ All tables dropped")
        
        print("🔨 Creating fresh tables...")
        await init_db()
        print("✅ Tables created")
        
        print("📊 Loading seed data (335 transactions)...")
        async with AsyncSessionLocal() as session:
            await seed_database(session)
        print("✅ Seed data loaded")
        
        print("\n" + "=" * 60)
        print("✅ Database reset complete!")
        print("=" * 60)
        print("\nDatabase file: finai.db")
        print("Next: Start server with: python dev_start.py")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Verify we're in the backend directory
    if not Path("main.py").exists():
        print("❌ Error: main.py not found. Are you in the 'backend' directory?")
        sys.exit(1)
    
    # Check if .env exists
    if not Path(".env").exists() and not Path(".env.local").exists():
        print("⚠️  .env file not found!")
        print("  Copy .env.example to .env and configure it first")
        sys.exit(1)
    
    print("=" * 60)
    print("FinAI Database Reset")
    print("=" * 60)
    print()
    print("⚠️  WARNING: This will DELETE all data in finai.db")
    response = input("Are you sure? (yes/no): ")
    
    if response.lower() != "yes":
        print("❌ Cancelled")
        sys.exit(1)
    
    print()
    asyncio.run(reset_database())
