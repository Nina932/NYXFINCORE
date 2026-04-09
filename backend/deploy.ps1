# FinAI Deployment Helper for Windows PowerShell
# Usage: .\deploy.ps1 [setup|start|stop|logs|status|backup|restore]

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    
    [Parameter(Position=1)]
    [string]$Argument = ""
)

# Helper functions
function Write-Error-Custom {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️  $Message" -ForegroundColor Yellow
}

function Test-Docker {
    $docker = docker --version 2>$null
    if ($null -eq $docker) {
        Write-Error-Custom "Docker not found. Install from https://docs.docker.com/get-docker/"
        exit 1
    }
    Write-Success "Docker found: $docker"
}

function Test-Compose {
    $compose = docker compose version 2>$null
    if ($null -eq $compose) {
        Write-Error-Custom "Docker Compose not found."
        exit 1
    }
    Write-Success "Docker Compose ready"
}

function Setup {
    Write-Info "Setting up FinAI..."
    
    # Check if .env exists
    if (Test-Path ".env") {
        Write-Info ".env already exists, skipping copy"
    } else {
        if (-not (Test-Path ".env.example")) {
            Write-Error-Custom ".env.example not found"
            exit 1
        }
        Copy-Item ".env.example" ".env"
        Write-Success ".env created from template"
        Write-Info "Edit .env with your configuration before running start"
    }
    
    # Create directories
    @("static", "uploads", "exports", "logs", "ssl", "backups") | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -ItemType Directory -Force -Path $_ | Out-Null
            Write-Success "Created directory: $_"
        }
    }
    
    Write-Info "Setup complete!"
    Write-Info "Next steps:"
    Write-Info "1. Edit .env with your API key and database password"
    Write-Info "2. Copy FinAI_Platform_v7.html to static/ folder"
    Write-Info "3. Run: .\deploy.ps1 start"
}

function Start-FinAI {
    Test-Docker
    Test-Compose
    
    if (-not (Test-Path ".env")) {
        Write-Error-Custom ".env not found. Run: .\deploy.ps1 setup"
        exit 1
    }
    
    Write-Info "Starting FinAI stack..."
    docker compose up -d
    
    Write-Info "Waiting for services to start..."
    Start-Sleep -Seconds 5
    
    docker compose ps
    
    Write-Success "FinAI started!"
    Write-Info "Access your app:"
    Write-Info "  Frontend: http://localhost"
    Write-Info "  API Docs: http://localhost:8000/api/docs"
    Write-Info "  Health:   http://localhost:8000/health"
}

function Stop-FinAI {
    Write-Info "Stopping FinAI..."
    docker compose down
    Write-Success "FinAI stopped"
}

function Show-Logs {
    param([string]$Container = "api")
    docker compose logs -f $Container
}

function Show-Status {
    docker compose ps
}

function Backup-DB {
    Write-Info "Backing up database..."
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFile = "backups\finai_backup_$timestamp.sql"
    
    if (-not (Test-Path "backups")) {
        New-Item -ItemType Directory -Path "backups" | Out-Null
    }
    
    try {
        docker compose exec -T db pg_dump -U finai finai_db | Out-File $backupFile
        Write-Success "Backup created: $backupFile"
    } catch {
        Write-Error-Custom "Backup failed: $_"
        exit 1
    }
}

function Restore-DB {
    param([string]$BackupFile)
    
    if ([string]::IsNullOrEmpty($BackupFile)) {
        Write-Error-Custom "Usage: .\deploy.ps1 restore <backup_file>"
        Write-Info "Available backups:"
        Get-ChildItem "backups\" -ErrorAction SilentlyContinue | Format-Table Name, LastWriteTime
        exit 1
    }
    
    if (-not (Test-Path $BackupFile)) {
        Write-Error-Custom "Backup file not found: $BackupFile"
        exit 1
    }
    
    Write-Info "Restoring database from $BackupFile..."
    $backup = Get-Content $BackupFile -Raw
    $backup | docker compose exec -T db psql -U finai finai_db
    Write-Success "Database restored from $BackupFile"
}

function Test-Health {
    Write-Info "Checking API health..."
    
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -ErrorAction Stop
        Write-Success "API is healthy"
        Write-Host ($health | ConvertTo-Json)
    } catch {
        Write-Error-Custom "API is not responding: $_"
        exit 1
    }
}

# Main switch
switch ($Command.ToLower()) {
    "setup" {
        Setup
    }
    "start" {
        Start-FinAI
    }
    "stop" {
        Stop-FinAI
    }
    "logs" {
        Show-Logs -Container $Argument
    }
    "status" {
        Show-Status
    }
    "backup" {
        Backup-DB
    }
    "restore" {
        Restore-DB -BackupFile $Argument
    }
    "health" {
        Test-Health
    }
    default {
        Write-Host "FinAI Deployment Helper for Windows" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Usage: .\deploy.ps1 [command] [arguments]" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Commands:" -ForegroundColor Green
        Write-Host "  setup                  - Initialize configuration (.env, directories)"
        Write-Host "  start                  - Start all services (API, DB, Nginx)"
        Write-Host "  stop                   - Stop all services"
        Write-Host "  status                 - Show container status"
        Write-Host "  logs [container]       - View logs (default: api)"
        Write-Host "  health                 - Check API health"
        Write-Host "  backup                 - Backup database"
        Write-Host "  restore <file>         - Restore database from backup"
        Write-Host ""
        Write-Host "Examples:" -ForegroundColor Cyan
        Write-Host "  .\deploy.ps1 setup"
        Write-Host "  .\deploy.ps1 start"
        Write-Host "  .\deploy.ps1 logs api"
        Write-Host "  .\deploy.ps1 backup"
        Write-Host "  .\deploy.ps1 restore backups\finai_backup_20250304_120000.sql"
        exit 1
    }
}
