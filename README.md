<div align="center">

# ðŸ›¡ï¸ SentinelAI
### Intelligent Infrastructure Monitoring â€¢ Predictive Health & Incident Intelligence

**Collect telemetry. Detect anomalies. Score system health. Explain incidents with local AI, all in one dashboard.**

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Google Gemma](https://img.shields.io/badge/Gemma%204-gemma--4--26b--a4b--it-4285F4?style=for-the-badge&logo=google&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-Isolation%20Forest-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Storage-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-Charts-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)

![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)
![Tests](https://img.shields.io/badge/tests-359%20passed-brightgreen?logo=pytest&logoColor=white)
![Code Style](https://img.shields.io/badge/code%20style-PEP%208-brightgreen)

[Features](#-features) â€¢ [Architecture](#-architecture) â€¢ [Demo Guide](docs/HACKATHON_DEMO_GUIDE.md) â€¢ [Deployment](docs/DEPLOYMENT_AND_TROUBLESHOOTING.md) â€¢ [Quick Start](#-quick-start) â€¢ [Dashboard](#-dashboard)

</div>


---

> [!IMPORTANT]
> **Scope note:** Anomaly detection and resource-based risk indicators describe *observed system behavior*. They do **not** establish a validated probability that a hardware or operating-system failure will occur. Reliable failure prediction requires representative, labeled failure-event data.

## ðŸ“– Overview

**SentinelAI** is an AI-augmented server health monitoring platform that observes the operational telemetry of computing infrastructure, detects multi-metric behavioral anomalies, and presents explainable, evidence-grounded risk intelligence.

It pairs a low-overhead host telemetry collection pipeline with a 39-feature **Isolation Forest** machine learning model, a state-of-the-art **Google Gemma 4 (`gemma-4-26b-a4b-it`)** LLM via the Google Gemini API for incident diagnostics, an instant **deterministic fallback engine**, and strict **OS-aware safety guardrails** (autonomous command execution is permanently disabled).

It also ships with **deterministic simulation scenarios**, allowing operators and judges to observe incident diagnostics under CPU spikes, memory leaks, or disk saturation **without stressing real machine hardware**.

## ðŸ“¸ Preview

<!-- Add your screenshots to docs/screenshots/ and update the paths below -->
<div align="center">

| System Overview | Health & Risk Analysis |
| :---: | :---: |
| ![Overview](docs/screenshots/overview.png) | ![Health](docs/screenshots/health.png) |

| Historical Telemetry | Simulation & Diagnostics |
| :---: | :---: |
| ![History](docs/screenshots/history.png) | ![Simulation](docs/screenshots/simulation.png) |

</div>

## âœ¨ Features

| | Feature | Description |
| :-: | --- | --- |
| ðŸ“¡ | **Telemetry collection** | CPU, memory, disk, network activity, and running processes via `psutil` |
| ðŸ§¹ | **Validation & cleaning** | Handles missing, invalid, and non-finite metric values |
| ðŸ§® | **Feature engineering** | 39-feature vectors: rolling stats, sample deltas, process usage, and time signals |
| ðŸ—„ï¸ | **Historical storage** | Metrics, feature vectors, and validation records persisted in SQLite WAL mode |
| ðŸ¤– | **Anomaly detection** | Isolation Forest flags telemetry outliers against learned baselines |
| ðŸ’¯ | **Health score (0â€“100)** | Deterministic score calculated from anomaly probability and resource stress |
| ðŸš¦ | **Risk categories** | Normal Â· Low Â· Moderate Â· High Â· Critical |
| ðŸ§  | **AI Incident Diagnostics** | Google Gemma 4 (`gemma-4-26b-a4b-it`) incident summarization, root causes, and runbooks |
| ðŸ›¡ï¸ | **Deterministic Fallback** | Instant (<60ms) rule-based diagnosis when Ollama is offline or times out |
| ðŸ”’ | **AI Safety & Human Review** | OS-aware dangerous-command filtering; zero autonomous destructive execution |
| ðŸ“Š | **Interactive dashboard** | Live gauges, multi-metric time series, anomaly audits, and DB inspector |
| â±ï¸ | **Live & background monitoring** | One-off snapshots or periodic background collection loops |
| ðŸ§ª | **Safe simulation** | Synthetic CPU, memory, disk, network, combined-pressure, and baseline scenarios |
| ðŸš€ | **FastAPI REST API** | Async endpoints for telemetry, ML scoring, simulation, and AI diagnostics |
| ðŸ©º | **Operational status** | Real-time probes distinguishing API health from Ollama model reachability |
| ðŸ“¤ | **CSV exports** | Download monitoring and diagnostic data for offline analysis |
| ðŸ’¾ | **Model management** | Atomic serialization with feature-schema validation and heuristic fallback |
| âœ… | **Automated testing** | 344 passing tests (334 core backend/API/ML tests + 10 Playwright E2E tests) |

## ðŸ—ï¸ Architecture

### Data flow

```mermaid
flowchart TD
    A[ðŸ–¥ï¸ Host Operating System] --> B[ðŸ“¡ Metric Collectors]
    B --> C[ðŸ§¹ Validation & Preprocessing]
    C --> D[ðŸ§® Feature Engineering]
    D --> E[(ðŸ—„ï¸ SQLite Historical Storage)]
    D --> F[ðŸ¤– Anomaly Detection & Health Analysis]
    F --> G[ðŸš¦ Risk Categorization & Diagnostics]
    G --> H[ðŸ“Š Streamlit Dashboard]
    G --> I[ðŸ“¤ CSV Exports]
    E --> H
```

### Project structure

```text
SentinelAI/
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ core/                 # Configuration and logging
â”‚   â”œâ”€â”€ models/               # Telemetry data models
â”‚   â”œâ”€â”€ collectors/           # System metrics collection
â”‚   â”œâ”€â”€ preprocessing/        # Data validation and feature engineering
â”‚   â”œâ”€â”€ database/             # SQLite persistence
â”‚   â”œâ”€â”€ ml/                   # ML, simulation, health scoring
â”‚   â”œâ”€â”€ ai/                   # LLM client, safety layer, diagnostic service
â”‚   â”œâ”€â”€ api/                  # FastAPI REST endpoints and routers
â”‚   â”œâ”€â”€ dashboard/            # Streamlit dashboard
â”‚   â””â”€â”€ utils/                # Shared utilities
â”œâ”€â”€ frontend/                 # React + TypeScript frontend
â”œâ”€â”€ data/                     # Local telemetry database
â”œâ”€â”€ models/                   # ML model artifacts
â”œâ”€â”€ logs/                     # Application logs
â”œâ”€â”€ scripts/                  # Reproducible PowerShell launch & shutdown scripts
â”œâ”€â”€ docs/                     # Guides, architecture, and hackathon demo script
â”œâ”€â”€ tests/                    # Unit, integration and E2E Playwright tests
â”œâ”€â”€ .env.example              # Example configuration
â”œâ”€â”€ requirements.txt          # Python dependencies
â”œâ”€â”€ run.py                    # CLI telemetry entry point
â”œâ”€â”€ run_api.py                # Standalone FastAPI launcher
â””â”€â”€ README.md
```

## ðŸ§° Tech Stack

| Area | Technology |
| --- | --- |
| Language | Python 3.12+ |
| System metrics | `psutil` |
| Machine learning | `scikit-learn` |
| Data processing | `numpy`, `pandas` |
| Dashboard | `Streamlit` |
| Visualizations | `Plotly` |
| Database | SQLite |
| Model serialization | `joblib` |
| Configuration | `python-dotenv` |
| Testing | `pytest` |

## ðŸš€ Quick Start

**Requirements:** Python 3.12+ Â· Node.js and npm Â· Windows (current setup is Windows-focused) Â· Git (optional)

### 1. Clone the repository

```powershell
git clone https://github.com/andhony07/AI-Based-Server-Health-Monitoring.git
cd AI-Based-Server-Health-Monitoring
```

### 2. Set up the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` if your configuration requires changes. Do not commit secrets.

### 4. Launch SentinelAI (Recommended)

To start both the FastAPI backend and Streamlit dashboard with prerequisite checks and port verification:

```powershell
.\scripts\start_sentinelai.ps1
```

To run pre-flight environment checks without starting background processes:
```powershell
.\scripts\start_sentinelai.ps1 -CheckOnly
```

To safely shut down both services:
```powershell
.\scripts\stop_sentinelai.ps1
```

---

### Alternative: Manual Multi-Terminal Launch

If you prefer interactive console logs in separate windows:

**Terminal 1 (FastAPI REST Backend):**
```powershell
.\.venv\Scripts\Activate.ps1
python run_api.py
```
*API is available at **http://127.0.0.1:8000** (Swagger documentation: **http://127.0.0.1:8000/docs**).*

**Terminal 2 (Streamlit Dashboard):**
```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app/dashboard/dashboard_main.py
```
*Dashboard is available at **http://localhost:8501**.*

**Optional: Ollama Local LLM (for live AI diagnostics):**
```powershell
ollama serve
# Verify qwen2.5:3b is available:
ollama list
```
*(If Ollama is stopped or unavailable, SentinelAI automatically activates its deterministic fallback engine without crashing or degrading ML scoring).*

---

## ðŸ“– Documentation & Guides

- **[Hackathon Demonstration Script](docs/HACKATHON_DEMO_GUIDE.md)**: 5â€“7 minute step-by-step judge walkthrough covering normal health monitoring, synthetic anomaly simulation, ML health updates, AI incident diagnosis, deterministic fallback, and human-in-the-loop safety.
- **[Deployment & Troubleshooting Guide](docs/DEPLOYMENT_AND_TROUBLESHOOTING.md)**: Detailed environment configuration, port resolution, Ollama troubleshooting, test execution, and safe shutdown reference.
- **[System Architecture](docs/architecture.md)**: Deep dive into the collectors, 39-feature pipeline, SQLite WAL persistence, Isolation Forest ML scoring, FastAPI REST layer, and AI Diagnostic Assistant.

## ðŸ› ï¸ Command Reference

| Goal | Command |
| --- | --- |
| Launch all services (Automated) | `.\scripts\start_sentinelai.ps1` |
| Pre-flight check only | `.\scripts\start_sentinelai.ps1 -CheckOnly` |
| Safe shutdown | `.\scripts\stop_sentinelai.ps1` |
| Launch Streamlit dashboard | `python -m streamlit run app/dashboard/dashboard_main.py` |
| Launch FastAPI backend | `python run_api.py` |
| Continuous telemetry loop | `python run.py` |
| Capture one telemetry snapshot | `python run.py --single-shot` |
| Train anomaly detection model | `python run.py --train` |
| Run core test suite | `pytest` |
| Run Playwright E2E test suite | `python -m pytest tests/e2e/test_dashboard_playwright.py` |

## ðŸ“Š Dashboard

| View | What you get |
| --- | --- |
| ðŸ  **System Overview** | Current status plus CPU, memory, disk, network, and process metrics |
| â¤ï¸ **Health & Risk Analysis** | Health score, anomaly score, risk category, and score breakdown |
| â±ï¸ **Real-Time Monitoring** | On-demand snapshots and background monitoring controls |
| ðŸ“ˆ **Historical Telemetry** | Stored metrics over selectable time ranges |
| ðŸš¨ **Anomaly Audit Log** | Historical anomaly scores and risk categories |
| ðŸ§ª **Simulation & Diagnostics** | Run synthetic scenarios and inspect evidence and recommendations |
| ðŸ©º **Operational Status** | Component status, worker state, and telemetry freshness |
| ðŸ“¤ **CSV Export** | Download supported records for offline analysis |
| ðŸ—„ï¸ **Database Inspection** | Record counts, sample timestamps, database size, recent records |

> An idle worker or stale telemetry may simply mean monitoring has not recently collected a sample.

## ðŸ§  How the Analysis Works

<details>
<summary><b>ðŸ“¡ Collected metrics</b></summary>

- **CPU:** overall utilization and core information
- **Memory:** total, used, available, and utilization
- **Disk:** total, used, free, and utilization
- **Network:** bytes sent/received and throughput
- **Processes:** process count and resource usage of top processes

</details>

<details>
<summary><b>ðŸ§® Feature engineering</b></summary>

The preprocessing pipeline builds a numerical feature vector from current utilization, changes between samples, rolling-window statistics, process usage, time indicators, and flags for missing metric domains. The exact schema is defined by the implementation and must stay consistent with the saved model artifacts.

</details>

<details>
<summary><b>ðŸ¤– Machine learning & risk analysis</b></summary>

An **Isolation Forest** identifies telemetry that differs from patterns in the training data. Its anomaly score is shown separately from the **health score** (a deterministic indicator based on configured penalties) and the **risk category** (configured thresholds over current conditions).

These outputs describe observed behavior. They are **not** calibrated probabilities of future failure.

</details>

## ðŸ§ª Simulation & Diagnostics

Deterministic synthetic scenarios for demos and regression testing:

`CPU spike` Â· `Memory pressure` Â· `Disk saturation` Â· `Network saturation` Â· `Combined resource pressure` Â· `Normal baseline`

Simulation feeds synthetic telemetry into the analysis pipeline. It **does not** exhaust real host resources or inject OS faults. Diagnostic recommendations are troubleshooting guidance based on available evidence, not proof of a root cause.

## ðŸ’¾ Data Storage

Telemetry is stored locally in SQLite (default: `data/system_metrics.db`). It holds metric snapshots, engineered feature vectors, and preprocessing validation records. Transactions keep related records consistent, and retention cleanup is supported. The database is local to the machine running the app.

<details>
<summary><b>Check how many samples you have collected</b></summary>

```powershell
python -c "import sqlite3; conn = sqlite3.connect('data/system_metrics.db'); print('Samples:', conn.execute('SELECT COUNT(*) FROM system_metrics').fetchone()[0]); conn.close()"
```

</details>

## âš™ï¸ Configuration

Settings live in `.env` (see `.env.example`): application metadata, logging, collection intervals, process limits, preprocessing, and database behavior.

## âœ… Testing

```powershell
pytest
```

The latest reported run: **237 passed**. Coverage spans configuration, collectors, preprocessing, database, machine learning, dashboard services, simulation, diagnostics, operational status, CSV export, and integration behavior. Tests verify software behavior; they do not demonstrate predictive accuracy on real hardware failures.

## âš ï¸ Scope & Limitations

- Isolation Forest flags deviations from the training baseline; it does not predict failures.
- The health score and risk categories reflect *current observed conditions*.
- Without a trained model or enough history, a heuristic fallback may be used where implemented.
- Simulated scenarios are for demonstration and testing, not authentic hardware-failure events.
- No validated probability or time-to-failure is estimated, since no labeled real-world failure data is used.

A supervised failure-prediction model would need suitable labeled data, a defined prediction horizon, and evaluation on held-out data that avoids temporal leakage.

## ðŸ‘¤ Author

**Andhony Saviyar S** Â· [@andhony07](https://github.com/andhony07)

---

<div align="center">

â­ If you find this project useful, consider giving it a star!

</div>
