#!/usr/bin/env python
"""
FinAI Development Server Starter
Starts the FastAPI development server with auto-reload
Usage: python dev_start.py
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    # Verify we're in the backend directory
    if not Path("main.py").exists():
        print("❌ Error: main.py not found. Are you in the 'backend' directory?")
        sys.exit(1)
    
    # Check if .env exists
    if not Path(".env").exists() and not Path(".env.local").exists():
        print("⚠️  Warning: .env file not found")
        print("  Copy .env.example to .env and set ANTHROPIC_API_KEY")
        print("  Or copy .env.local to .env")
        response = input("Create .env from .env.example? (y/n): ")
        if response.lower() == 'y':
            if Path(".env.example").exists():
                import shutil
                shutil.copy(".env.example", ".env")
                print("✅ Created .env from .env.example")
                print("📝 Please edit .env and set ANTHROPIC_API_KEY")
            else:
                print("❌ .env.example not found")
                sys.exit(1)
        else:
            print("❌ .env file required. Exiting.")
            sys.exit(1)
    
    # Create necessary directories
    for directory in ["uploads", "exports", "logs"]:
        Path(directory).mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🚀 FinAI Development Server")
    print("=" * 60)
    print()
    print("✅ Starting FastAPI development server...")
    print()
    print("📍 Access points:")
    print("   Frontend: Open FinAI_Platform_v7.html in your browser")
    print("   API Docs: http://localhost:8000/api/docs")
    print("   Health:   http://localhost:8000/health")
    print()
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    # Start the development server
    try:
        subprocess.run([
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--reload",
            "--host",
            "0.0.0.0",
            "--port",
            "8000"
        ])
    except KeyboardInterrupt:
        print("\n✋ Development server stopped")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Check if Python 3.12+ is installed: python --version")
        print("   2. Check if venv is activated")
        print("   3. Check if all dependencies are installed: pip install -r requirements.txt")
        print("   4. Check .env file configuration")
        sys.exit(1)

if __name__ == "__main__":
    main()
