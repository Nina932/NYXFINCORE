#!/usr/bin/env python
"""
FinAI Git Repository Setup
Initializes git repository and configures remote
Usage: python setup_git.py
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command and handle errors."""
    print(f"▶️  {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️  {result.stderr}")
            return False
        print(f"✅ {description}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    # Verify we're in the backend directory
    if not Path("main.py").exists():
        print("❌ Error: main.py not found. Are you in the 'backend' directory?")
        sys.exit(1)
    
    print("=" * 60)
    print("FinAI Git Repository Setup")
    print("=" * 60)
    print()
    
    # Check if .git already exists
    if Path(".git").exists():
        print("⚠️  Git repository already initialized")
        response = input("Reinitialize? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled")
            sys.exit(0)
    
    # Get GitHub repository URL
    default_repo = "https://github.com/Nina932/fina.git"
    print(f"\nGitHub Repository URL")
    print(f"Default: {default_repo}")
    repo_url = input("Enter repository URL (press Enter for default): ").strip()
    if not repo_url:
        repo_url = default_repo
    
    # Get user info
    print()
    user_name = input("Enter your Git name: ").strip()
    user_email = input("Enter your Git email: ").strip()
    
    if not user_name or not user_email:
        print("❌ Name and email are required")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("Starting Git Setup...")
    print("=" * 60)
    print()
    
    # Initialize repository
    if not Path(".git").exists():
        if not run_command("git init", "Initialize git repository"):
            sys.exit(1)
    
    # Configure user
    if not run_command(f'git config user.name "{user_name}"', "Configure user name"):
        sys.exit(1)
    
    if not run_command(f'git config user.email "{user_email}"', "Configure user email"):
        sys.exit(1)
    
    # Check if remote already exists
    result = subprocess.run("git remote get-url origin", shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        old_url = result.stdout.strip()
        print(f"⚠️  Remote 'origin' already exists: {old_url}")
        if old_url != repo_url:
            response = input(f"Update to {repo_url}? (yes/no): ")
            if response.lower() == "yes":
                run_command(f"git remote remove origin", "Remove old remote")
                run_command(f'git remote add origin "{repo_url}"', "Add new remote")
    else:
        if not run_command(f'git remote add origin "{repo_url}"', "Add remote repository"):
            sys.exit(1)
    
    # Create main branch if needed
    result = subprocess.run("git branch", shell=True, capture_output=True, text=True)
    if "main" not in result.stdout and "master" not in result.stdout:
        run_command("git branch -M main", "Create main branch")
    
    # Show status
    print()
    print("=" * 60)
    print("✅ Git Setup Complete!")
    print("=" * 60)
    print()
    
    # Verify setup
    print("Configuration:")
    subprocess.run("git config --local user.name", shell=True)
    subprocess.run("git config --local user.email", shell=True)
    subprocess.run("git remote -v", shell=True)
    
    print()
    print("Next steps:")
    print("1. git add .")
    print("2. git commit -m 'Initial commit: FinAI Backend v2.0.0'")
    print("3. git push -u origin main")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)
