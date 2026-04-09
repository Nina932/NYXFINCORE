# FinAI Development Setup for Windows (Manual)

**Issue**: Terminal hangs during `pip install`. This guide avoids that.

---

## Solution: Manual Step-by-Step Setup

### Step 1: Open PowerShell as Administrator

1. Press `Win + X` → Select **Windows PowerShell (Admin)**
2. Allow execution policy:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
   (Type `Y` and press Enter)

3. Navigate to the project:
   ```powershell
   cd C:\Users\Nino\Downloads\FinAI_Backend_3\backend
   ```

---

### Step 2: Create Virtual Environment

```powershell
python -m venv venv
```

**Wait**: This takes 5-15 seconds. You will see NO output. That's normal.

When it finishes (prompt returns), you'll see:
```
C:\Users\Nino\Downloads\FinAI_Backend_3\backend>
```

---

### Step 3: Activate Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

**Important**: After this, your prompt should change to:
```
(venv) C:\Users\Nino\Downloads\FinAI_Backend_3\backend>
```

The `(venv)` prefix means activation worked. **If you don't see it, rerun the command.**

---

### Step 4: Upgrade pip

```powershell
python -m pip install --upgrade pip
```

**Wait**: 10-20 seconds. Again, minimal output is normal.

---

### Step 5: Install Requirements (The Long One)

```powershell
pip install -r requirements.txt
```

⚠️ **CRITICAL**: 
- **This will take 3-10 minutes** (downloading + compiling packages)
- **Do NOT close the window**
- **Do NOT interrupt** (no Ctrl+C)
- Let it finish completely

You'll see lines like:
```
Collecting fastapi==0.115.5
Downloading fastapi-0.115.5-py3-none-any.whl (95 kB)
Installing collected packages: ...
Successfully installed fastapi-0.115.5
```

When finished, the prompt returns:
```
(venv) C:\Users\Nino\Downloads\FinAI_Backend_3\backend>
```

---

### Step 6: Verify Installation

```powershell
pip show pydantic
pip show fastapi
```

You should see:
```
Name: pydantic
Version: 2.10.3
```

If these commands show "WARNING: Package(s) not found", **rerun Step 5** more slowly (watch for errors).

---

### Step 7: Start Development Server

```powershell
python dev_start.py
```

You should see:
```
🚀 FinAI Development Server
============================================================

✅ Starting FastAPI development server...

📍 Access points:
   API Docs: http://localhost:8000/api/docs
```

**Success!** Keep this window open.

---

### Step 8: Access the API

Open your browser and go to:
```
http://localhost:8000/api/docs
```

You should see the Swagger UI with all API endpoints.

---

## If Something Goes Wrong

### Error: "ModuleNotFoundError: No module named 'pydantic'"

**Cause**: Step 5 (pip install) didn't complete  
**Fix**: 
1. Check if `(venv)` is in your prompt
2. Rerun Step 5 **slowly** watching for red text/errors
3. If you see errors about "Microsoft C++ build tools", continue anyway (usually non-fatal)

### Error: "bash: ./venv/Scripts/Activate.ps1: No such file or directory"

**Cause**: You're in bash, not PowerShell  
**Fix**: You need to use PowerShell, not Git Bash. Start over with:
```powershell
# In PowerShell
cd C:\Users\Nino\Downloads\FinAI_Backend_3\backend
.\venv\Scripts\Activate.ps1
```

### Error: "Cannot be loaded because running scripts is disabled"

**Cause**: Execution policy not set  
**Fix**: In elevated PowerShell, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### pip install keeps hanging/freezing

**Cause**: Network timeout or slow disk  
**Fix**: Try this instead:
```powershell
pip install -r requirements.txt --no-cache-dir --disable-pip-version-check
```

Or install packages individually:
```powershell
pip install fastapi==0.115.5
pip install uvicorn[standard]==0.32.1
pip install sqlalchemy==2.0.36
# ... etc
```

---

## Automated Alternative

If you want to use the automated script instead:

1. In PowerShell (elevated), from the backend folder:
   ```powershell
   .\setup_windows.ps1
   ```

2. If prompted about execution policy:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. Then run the script again:
   ```powershell
   .\setup_windows.ps1
   ```

---

## Quick Reference

```powershell
# Enter project folder
cd C:\Users\Nino\Downloads\FinAI_Backend_3\backend

# Activate venv (do this every time you start PowerShell)
.\venv\Scripts\Activate.ps1

# Start dev server (after activating venv)
python dev_start.py

# Reset database
python reset_db.py

# Run tests
pytest tests/ -v

# Set up GitHub
python setup_git.py
```

---

## Your Current State

✓ Project files: Ready  
✓ requirements.txt: Ready  
✗ Virtual environment: **Needs creation (follow Step 1-7 above)**  
✗ Dependencies: **Needs installation (Step 5)**  
✗ Server: **Needs startup (Step 7)**  

---

## Next Steps After Setup

1. ✅ Follow Steps 1-7 above
2. ✅ Keep dev server running in this PowerShell
3. ✅ Open new PowerShell for other commands
4. ✅ Visit http://localhost:8000/api/docs
5. ✅ Run `python setup_git.py` in second PowerShell to set up GitHub

---

**Estimated total time**: 20-30 minutes (mostly waiting for Step 5)  
**What you'll have**: Fully working local dev environment ✓

Let me know when you get stuck (include the red error text)!
