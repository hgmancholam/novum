# Novum Development Runner
# Usage: .\scripts\dev.ps1 [backend|frontend|all]

param(
    [Parameter(Position = 0)]
    [ValidateSet("backend", "frontend", "all")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Start-Backend {
    Write-Host "Starting backend..." -ForegroundColor Cyan
    Push-Location "$RepoRoot\backend"
    try {
        if (-not (Test-Path ".venv")) {
            Write-Host "Creating virtual environment..." -ForegroundColor Yellow
            uv venv
        }
        Write-Host "Syncing dependencies..." -ForegroundColor Yellow
        uv sync
        Write-Host "Starting uvicorn..." -ForegroundColor Green
        uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    }
    finally {
        Pop-Location
    }
}

function Start-Frontend {
    Write-Host "Starting frontend..." -ForegroundColor Cyan
    Push-Location "$RepoRoot\frontend"
    try {
        if (-not (Test-Path "node_modules")) {
            Write-Host "Installing dependencies..." -ForegroundColor Yellow
            npm install
        }
        Write-Host "Starting Vite..." -ForegroundColor Green
        npm run dev
    }
    finally {
        Pop-Location
    }
}

switch ($Target) {
    "backend" {
        Start-Backend
    }
    "frontend" {
        Start-Frontend
    }
    "all" {
        Write-Host "Starting both backend and frontend..." -ForegroundColor Cyan
        Write-Host "Run in separate terminals:" -ForegroundColor Yellow
        Write-Host "  Terminal 1: .\scripts\dev.ps1 backend" -ForegroundColor White
        Write-Host "  Terminal 2: .\scripts\dev.ps1 frontend" -ForegroundColor White
    }
}
