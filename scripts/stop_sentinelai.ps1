<#
.SYNOPSIS
    SentinelAI Safe Service Terminator (PowerShell).

.DESCRIPTION
    Identifies and stops only the specific SentinelAI FastAPI and Streamlit
    processes bound to ports 8000 and 8501. Never terminates unrelated
    system or user processes.

.EXAMPLE
    .\scripts\stop_sentinelai.ps1
#>

[CmdletBinding()]
param()

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SentinelAI Safe Service Shutdown" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$TargetPorts = @(8000, 8081, 8501)
$TerminatedCount = 0

foreach ($port in $TargetPorts) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $pidToStop = $conn.OwningProcess
            # Verify process exists and is a python/uvicorn/streamlit process
            $proc = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue
            if ($proc) {
                $procName = $proc.ProcessName.ToLower()
                if ($procName -like "*python*" -or $procName -like "*uvicorn*" -or $procName -like "*streamlit*") {
                    Write-Host "Stopping SentinelAI service on port $port (PID: $pidToStop, Name: $($proc.ProcessName))..." -ForegroundColor Yellow
                    try {
                        Stop-Process -Id $pidToStop -Force -ErrorAction Stop
                        Write-Host "[OK] Stopped PID $pidToStop on port $port." -ForegroundColor Green
                        $TerminatedCount++
                    } catch {
                        Write-Host "[ERROR] Could not stop PID ${pidToStop}: $_" -ForegroundColor Red
                    }
                } else {
                    Write-Host "[NOTICE] Port $port is held by PID $pidToStop ($procName), which does not appear to be a Python process. Skipping for safety." -ForegroundColor Yellow
                }
            }
        }
    } else {
        Write-Host "Port $port is idle. No active service to terminate." -ForegroundColor Gray
    }
}

if ($TerminatedCount -gt 0) {
    Write-Host "`n[OK] SentinelAI services stopped cleanly ($TerminatedCount process(es) terminated)." -ForegroundColor Green
} else {
    Write-Host "`n[INFO] No active SentinelAI processes were running on ports 8000 or 8501." -ForegroundColor Gray
}

Write-Host "Note: If Ollama was started manually, its terminal window can be closed directly." -ForegroundColor Gray
Write-Host ""
