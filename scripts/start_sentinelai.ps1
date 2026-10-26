<#
.SYNOPSIS
    SentinelAI Reproducible Service Launcher (PowerShell).

.DESCRIPTION
    Validates virtual environment, configuration, and port prerequisites.
    Probes Ollama service availability and launches FastAPI and Streamlit
    services with accessible logging in the logs/ directory.

.PARAMETER CheckOnly
    Perform prerequisite and port validation without starting services.

.EXAMPLE
    .\scripts\start_sentinelai.ps1
    .\scripts\start_sentinelai.ps1 -CheckOnly
#>

[CmdletBinding()]
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

# 1. Resolve Project Root relative to script location
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $ProjectRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SentinelAI Service Launcher & Environment Diagnostic" -ForegroundColor Cyan
Write-Host "  Project Root: $ProjectRoot" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

# 2. Check Python Virtual Environment
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Python virtual environment not found at:" -ForegroundColor Red
    Write-Host "        $VenvPython" -ForegroundColor Red
    Write-Host "        Please create it using: python -m venv .venv" -ForegroundColor Yellow
    Write-Host "        Then install requirements: .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Virtual environment found: $VenvPython" -ForegroundColor Green

# 3. Check Required Core Files
$RequiredFiles = @(
    "run_api.py",
    "app\main.py",
    "app\dashboard\dashboard_main.py",
    "models\isolation_forest.joblib"
)

$MissingFiles = @()
foreach ($file in $RequiredFiles) {
    $fullPath = Join-Path $ProjectRoot $file
    if (-not (Test-Path $fullPath)) {
        $MissingFiles += $file
    }
}

if ($MissingFiles.Count -gt 0) {
    Write-Host "[ERROR] Missing critical application files:" -ForegroundColor Red
    foreach ($m in $MissingFiles) {
        Write-Host "        - $m" -ForegroundColor Red
    }
    Write-Host "        Ensure repository is intact or run training: .venv\Scripts\python.exe run.py --train" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Critical application files verified." -ForegroundColor Green

# Ensure logs and data directories exist
$LogsDir = Join-Path $ProjectRoot "logs"
$DataDir = Join-Path $ProjectRoot "data"
if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir | Out-Null }

# 4. Probe Port Availability (8000 and 8501)
$ApiPort = if ($env:API_PORT) { [int]$env:API_PORT } else { 8081 }
$DashboardPort = 8501

$ApiInUse = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
$DashboardInUse = Get-NetTCPConnection -LocalPort $DashboardPort -State Listen -ErrorAction SilentlyContinue

if ($ApiInUse) {
    $procId = $ApiInUse[0].OwningProcess
    $procName = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
    Write-Host "[WARNING] Port $ApiPort is already in use by PID $procId ($procName)." -ForegroundColor Yellow
} else {
    Write-Host "[OK] API Port $ApiPort is available." -ForegroundColor Green
}

if ($DashboardInUse) {
    $procId = $DashboardInUse[0].OwningProcess
    $procName = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
    Write-Host "[WARNING] Port $DashboardPort is already in use by PID $procId ($procName)." -ForegroundColor Yellow
} else {
    Write-Host "[OK] Dashboard Port $DashboardPort is available." -ForegroundColor Green
}

# 5. Probe Ollama Daemon Status (Port 11434)
$OllamaUrl = "http://127.0.0.1:11434"
$OllamaAvailable = $false
$ModelFound = $false

try {
    $resp = Invoke-RestMethod -Uri "$OllamaUrl/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
    $OllamaAvailable = $true
    $models = $resp.models | ForEach-Object { $_.name }
    if ($models -contains "qwen2.5:3b" -or ($models | Where-Object { $_ -like "qwen2.5*" })) {
        $ModelFound = $true
    }
} catch {
    $OllamaAvailable = $false
}

if ($OllamaAvailable -and $ModelFound) {
    Write-Host "[OK] Ollama daemon is ONLINE with model 'qwen2.5:3b' available." -ForegroundColor Green
} elseif ($OllamaAvailable -and -not $ModelFound) {
    Write-Host "[WARNING] Ollama is ONLINE, but model 'qwen2.5:3b' is not installed." -ForegroundColor Yellow
    Write-Host "          Run: ollama pull qwen2.5:3b" -ForegroundColor Yellow
    Write-Host "          SentinelAI will operate using deterministic fallback rules until the model is pulled." -ForegroundColor Yellow
} else {
    Write-Host "[NOTICE] Ollama daemon is OFFLINE at $OllamaUrl." -ForegroundColor Cyan
    Write-Host "         SentinelAI will start in DETERMINISTIC FALLBACK mode." -ForegroundColor Cyan
    Write-Host "         All dashboard views, ML models, and rule-based diagnostic runbooks remain 100% functional." -ForegroundColor Cyan
    Write-Host "         To enable live LLM inference, start Ollama in a separate terminal:" -ForegroundColor Gray
    Write-Host "           `$env:OLLAMA_MODELS = 'E:\Downloads\.ollama\models'; ollama serve" -ForegroundColor Gray
}

if ($CheckOnly) {
    Write-Host "`n[CheckOnly] Prerequisite validation completed successfully. No services were launched." -ForegroundColor Cyan
    exit 0
}

# 6. Launch Services
Write-Host "`nStarting SentinelAI Services..." -ForegroundColor Cyan
$env:PYTHONUNBUFFERED = "1"

# A. FastAPI Backend
if (-not $ApiInUse) {
    $ApiLogOut = Join-Path $LogsDir "api_stdout.log"
    $ApiLogErr = Join-Path $LogsDir "api_stderr.log"
    Write-Host "  -> Launching FastAPI backend on http://127.0.0.1:$ApiPort..." -ForegroundColor Gray
    $apiProcess = Start-Process -FilePath $VenvPython `
        -ArgumentList "-u", "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1", "--port", "$ApiPort" `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $ApiLogOut `
        -RedirectStandardError $ApiLogErr `
        -PassThru

    Start-Sleep -Seconds 2
    if ($apiProcess.HasExited) {
        Write-Host "[ERROR] FastAPI failed to start. Exit Code: $($apiProcess.ExitCode)" -ForegroundColor Red
        Write-Host "        Check logs at: $ApiLogErr" -ForegroundColor Red
    } else {
        Write-Host "[OK] FastAPI started (PID: $($apiProcess.Id)). Log: $ApiLogOut" -ForegroundColor Green
    }
} else {
    Write-Host "  -> FastAPI already running on port $ApiPort. Leaving existing instance active." -ForegroundColor Yellow
}

# B. Streamlit Dashboard
if (-not $DashboardInUse) {
    $StLogOut = Join-Path $LogsDir "streamlit_stdout.log"
    $StLogErr = Join-Path $LogsDir "streamlit_stderr.log"
    Write-Host "  -> Launching Streamlit dashboard on http://localhost:$DashboardPort..." -ForegroundColor Gray
    $stProcess = Start-Process -FilePath $VenvPython `
        -ArgumentList "-u", "-m", "streamlit", "run", "app/dashboard/dashboard_main.py", "--server.headless", "true", "--server.port", "$DashboardPort" `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $StLogOut `
        -RedirectStandardError $StLogErr `
        -PassThru

    Start-Sleep -Seconds 3
    if ($stProcess.HasExited) {
        Write-Host "[ERROR] Streamlit failed to start. Exit Code: $($stProcess.ExitCode)" -ForegroundColor Red
        Write-Host "        Check logs at: $StLogErr" -ForegroundColor Red
    } else {
        Write-Host "[OK] Streamlit started (PID: $($stProcess.Id)). Log: $StLogOut" -ForegroundColor Green
    }
} else {
    Write-Host "  -> Streamlit already running on port $DashboardPort. Leaving existing instance active." -ForegroundColor Yellow
}

# 7. Access Information
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SentinelAI is Ready" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  - Streamlit Dashboard : http://localhost:$DashboardPort" -ForegroundColor White
Write-Host "  - FastAPI Swagger Docs: http://localhost:$ApiPort/docs" -ForegroundColor White
Write-Host "  - API Liveness Probe  : http://localhost:$ApiPort/healthz" -ForegroundColor White
Write-Host "  - AI Diagnostic Status: http://localhost:$ApiPort/api/ai/status" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  To stop services cleanly, run: .\scripts\stop_sentinelai.ps1" -ForegroundColor Gray
Write-Host ""
