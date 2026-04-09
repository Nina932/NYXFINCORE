param()

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FinAI Development Setup for Windows" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Remove and (re)create virtual environment
Write-Host "[1/5] Recreating virtual environment (clean)..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "Removing existing venv..." -ForegroundColor Gray
    try {
        Remove-Item -Recurse -Force venv
    } catch {
        Write-Host "Warning: could not remove venv fully, continuing..." -ForegroundColor Yellow
    }
}

Write-Host "Creating venv..." -ForegroundColor Gray
python -m venv venv --clear
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create virtual environment. Ensure 'python' is on PATH." -ForegroundColor Red
    exit 1
}
Write-Host "Virtual environment created" -ForegroundColor Green

# Step 2: Locate venv python and pip
Write-Host "[2/5] Validating venv executables..." -ForegroundColor Yellow
$venvPython = Join-Path -Path (Get-Location) -ChildPath "venv\Scripts\python.exe"
$venvPip = Join-Path -Path (Get-Location) -ChildPath "venv\Scripts\pip.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: venv python not found at $venvPython" -ForegroundColor Red
    exit 1
}
Write-Host "Found venv python: $venvPython" -ForegroundColor Green

# If pip is missing, bootstrap it
if (-not (Test-Path $venvPip)) {
    Write-Host "pip not found in venv, bootstrapping pip via ensurepip..." -ForegroundColor Yellow
    & $venvPython -m ensurepip --upgrade
    if (-not (Test-Path $venvPip)) {
        Write-Host "ensurepip did not create pip. Attempting get-pip.py..." -ForegroundColor Yellow
        $getpip = Join-Path -Path $env:TEMP -ChildPath "get-pip.py"
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
        & $venvPython $getpip
        Remove-Item $getpip -Force
    }
}
if (-not (Test-Path $venvPip)) {
    Write-Host "ERROR: pip not available in venv after attempts." -ForegroundColor Red
    exit 1
}
Write-Host "pip available: $venvPip" -ForegroundColor Green

# Step 3: Upgrade pip inside venv
Write-Host "[3/5] Upgrading pip in venv..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip
Write-Host "Pip upgraded" -ForegroundColor Green

# Step 4: Install requirements using venv pip
Write-Host "[4/5] Installing requirements (this may take several minutes)..." -ForegroundColor Yellow
Write-Host "Do NOT close this window." -ForegroundColor Cyan
& $venvPip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install encountered errors. Re-run with verbose to see details:" -ForegroundColor Red
    Write-Host "  & $venvPip install -r requirements.txt --verbose" -ForegroundColor Gray
    exit 1
}
Write-Host "Requirements installed" -ForegroundColor Green

# Step 5: Final instructions
Write-Host "[5/5] Finalizing..." -ForegroundColor Yellow
Write-Host "To activate the venv in this window run:" -ForegroundColor White
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "Then start the dev server with:" -ForegroundColor White
Write-Host "  python dev_start.py" -ForegroundColor Gray
Write-Host "API docs: http://localhost:8000/api/docs" -ForegroundColor Cyan
Write-Host ""
