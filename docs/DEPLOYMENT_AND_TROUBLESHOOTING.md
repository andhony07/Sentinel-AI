# SentinelAI â€” Deployment, Configuration & Troubleshooting Guide

## 1. System Requirements & Tested Environment

SentinelAI is developed, benchmarked, and verified on Windows 10/11 environments:

| Component | Tested Version | Minimum Requirement | Notes |
| :--- | :--- | :--- | :--- |
| **Operating System** | Windows 11 Pro 64-bit | Windows 10 64-bit | Native PowerShell environment |
| **Python** | Python 3.12.10 | Python 3.10+ | Standard 64-bit CPython distribution |
| **Ollama Service** | Ollama 0.1.x+ | Any local Ollama release | Requires `ollama serve` |
| **Target LLM Model** | `qwen2.5:3b` (GGUF Q4_K_M) | 3B parameter model | ~1.9 GB download size |
| **Hardware** | Intel Core i5/i7 (4+ cores), 16GB RAM | 4 CPU cores, 8GB RAM | CPU inference tested locally |
| **Storage** | SSD storage recommended | 5GB free disk space | Database, models, virtual environment |

---

## 2. Environment Configuration

SentinelAI requires **zero configuration** to start with nominal defaults. All settings use sensible defaults that can be optionally overridden in a root-level `.env` file (copied from `.env.example`).

### Configuration Reference Table

| Variable | Default Value | Valid Options / Type | Purpose |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `development` | `development`, `testing`, `production` | Application lifecycle mode |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Structured logging verbosity |
| `METRIC_COLLECTION_INTERVAL` | `5.0` | Positive float (seconds) | Background telemetry probe cadence |
| `DATABASE_PATH` | `data/telemetry.db` | Filesystem path | SQLite database file location |
| `API_HOST` | `0.0.0.0` | IP string | FastAPI REST bind address |
| `API_PORT` | `8000` | Port integer (1024â€“65535) | REST API listening port |
| `DASHBOARD_PORT` | `8501` | Port integer (1024â€“65535) | Streamlit dashboard listening port |
| `AI_ENABLED` | `true` | `true`, `false` | Master toggle for AI diagnostic engine |
| `AI_PROVIDER` | `ollama` | `ollama`, `heuristic`, `mock` | Active inference provider |
| `AI_BASE_URL` | `http://localhost:11434` | HTTP/HTTPS URL | Local Ollama REST endpoint |
| `AI_MODEL_NAME` | `qwen2.5:3b` | Model tag string | Configured language model |
| `AI_TIMEOUT_SECONDS` | `90.0` | Positive float | Maximum latency before fallback |
| `AI_TEMPERATURE` | `0.2` | Float in range [0.0, 2.0] | Generation sampling temperature |

---

## 3. Ollama Setup & Model Verification

### Verifying Model Availability
Run:
```powershell
ollama list
```
Ensure `qwen2.5:3b` appears in the output. If missing, pull the model:
```powershell
ollama pull qwen2.5:3b
```

### Custom Model Storage Location
If model files reside on a non-default disk drive:
```powershell
$env:OLLAMA_MODELS = "E:\Downloads\.ollama\models"
ollama serve
```

### Validating Ollama Reachability
```powershell
curl.exe -s http://localhost:11434/api/tags
```

---

## 4. Starting SentinelAI Services

SentinelAI provides two deployment methods:

### Method A: Single-Command PowerShell Launcher (Recommended)

Run:
```powershell
.\scripts\start_sentinelai.ps1
```
This launcher:
1. Validates the `.venv` virtual environment and critical project files.
2. Probes ports 8000 and 8501 to prevent launching duplicate processes.
3. Probes Ollama reachability and confirms `qwen2.5:3b` presence.
4. Starts FastAPI (background) with output piped to `logs/api_stdout.log`.
5. Starts Streamlit (background) with output piped to `logs/streamlit_stdout.log`.
6. Prints all verified endpoints and access URLs.

To test prerequisites without starting processes:
```powershell
.\scripts\start_sentinelai.ps1 -CheckOnly
```

### Method B: Three-Terminal Manual Startup (Debugging & Live Output)

**Terminal 1 â€” Ollama Daemon**:
```powershell
$env:OLLAMA_MODELS = "E:\Downloads\.ollama\models"
ollama serve
```

**Terminal 2 â€” FastAPI REST Backend**:
```powershell
.venv\Scripts\python.exe run_api.py
```
*Listening on `http://127.0.0.1:8000` (Swagger docs: `/docs`)*

**Terminal 3 â€” Streamlit Dashboard**:
```powershell
.venv\Scripts\python.exe -m streamlit run app/dashboard/dashboard_main.py --server.port 8501
```
*Listening on `http://localhost:8501`*

---

## 5. Stopping SentinelAI Services

To terminate SentinelAI services cleanly without killing unrelated user or system processes:
```powershell
.\scripts\stop_sentinelai.ps1
```
This script queries ports 8000 and 8501, verifies the owning processes are Python/Streamlit/Uvicorn, and terminates only those specific PIDs.

---

## 6. Service Matrix & Feature Dependency Map

| Subsystem / Feature | Works Without Ollama? | Requires Live Ollama? | Behavior When Ollama is Offline |
| :--- | :---: | :---: | :--- |
| **System Telemetry Collection** | âœ… Yes | âŒ No | Fully operational via `psutil` kernel probes |
| **39-Feature Preprocessing Pipeline**| âœ… Yes | âŒ No | Fully operational with rolling statistics |
| **Isolation Forest Anomaly Detector**| âœ… Yes | âŒ No | Fully operational; calibrated anomaly score |
| **5-Tier Failure Risk Matrix** | âœ… Yes | âŒ No | Fully operational (Normal to Critical) |
| **Deterministic Anomaly Simulation**| âœ… Yes | âŒ No | Fully operational (6 reproducible profiles) |
| **SQLite Metric/Feature Storage** | âœ… Yes | âŒ No | Fully operational time-series persistence |
| **FastAPI REST Endpoints** | âœ… Yes | âŒ No | All telemetry, ML, and simulation routes online |
| **Diagnostic Incident Runbook** | âœ… Yes | âš ï¸ Optional | **Automatic deterministic fallback engages** |
| **Generative LLM Incident Runbook**| âŒ No | âœ… Yes | Engages when Ollama is running and responsive |

---

## 7. Troubleshooting Guide

### Issue 1: Port Conflict (Port 8000 or 8501 already in use)
- **Symptom**: `[WARNING] Port 8000 is already in use by PID XXXX`.
- **Diagnosis**: An earlier instance of Uvicorn or Streamlit is still running.
- **Remedy**:
  ```powershell
  .\scripts\stop_sentinelai.ps1
  ```
  Or inspect owning PID:
  ```powershell
  Get-NetTCPConnection -LocalPort 8000, 8501 -State Listen
  ```

### Issue 2: Ollama Connection Refused (`Cannot connect to Ollama daemon`)
- **Symptom**: API returns `is_fallback: true` with `Cannot connect to Ollama daemon at 'http://localhost:11434'`.
- **Diagnosis**: The Ollama background process is stopped.
- **Remedy**: Start Ollama in a separate terminal:
  ```powershell
  $env:OLLAMA_MODELS = "E:\Downloads\.ollama\models"
  ollama serve
  ```

### Issue 3: Missing Target Model (`qwen2.5:3b not found`)
- **Symptom**: Ollama is listening, but `/api/ai/status` reports `"model_available": false`.
- **Diagnosis**: The model tag has not been downloaded to the active `OLLAMA_MODELS` repository.
- **Remedy**:
  ```powershell
  ollama pull qwen2.5:3b
  ```

### Issue 4: Local CPU Inference Timeout
- **Symptom**: Diagnosis takes ~90 seconds and returns `is_fallback: true` with `"fallback_reason": "Ollama inference timed out after 90.0s."`.
- **Diagnosis**: High background CPU load or disk thrashing caused model generation to exceed 90 seconds.
- **Remedy**:
  1. Increase timeout in `.env`:
     ```ini
     AI_TIMEOUT_SECONDS=120.0
     ```
  2. Or warm the model by sending a short test request:
     ```powershell
     Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post -Body '{"model":"qwen2.5:3b","prompt":"ping","stream":false}' -ContentType "application/json"
     ```

### Issue 5: Playwright Browser Test Skips
- **Symptom**: Running `.venv\Scripts\pytest.exe -q` reports `10 skipped`.
- **Diagnosis**: Playwright is installed in the system Python environment (`C:\Users\dell5420\AppData\Local\Programs\Python\Python312`), not in `.venv`.
- **Remedy**: Run browser tests using the host Python environment where Playwright and browser binaries reside:
  ```powershell
  python -m pytest tests/e2e/test_dashboard_playwright.py -v
  ```

---

## 8. Automated Test Execution

### Core Backend & ML Regression Suite
```powershell
.venv\Scripts\pytest.exe -q
```
*Expected: 332 passed, 10 skipped (Playwright isolation), 0 failed.*

### Playwright End-to-End Suite
Ensure Streamlit is running on port 8501, then execute:
```powershell
python -m pytest tests/e2e/test_dashboard_playwright.py -v
```
*Expected: 10 passed in ~50s.*
