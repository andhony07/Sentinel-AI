# SentinelAI — Hackathon Demonstration Guide (5–7 Minute Walkthrough)

## Overview & Demo Goal

This guide provides an end-to-end, reproducible script for presenting **SentinelAI** to hackathon judges, evaluators, and technical reviewers.

**Key Selling Point**: SentinelAI bridges low-level kernel/hardware telemetry, unsupervised Machine Learning (Isolation Forest anomaly detection & health scoring), and local open-weight Generative AI (Ollama `qwen2.5:3b`) into an explainable incident response system. It features **100% deterministic fallback** and **strict OS-aware safety guardrails** (zero autonomous destructive execution).

---

## Pre-Flight Setup (Do 5 Minutes Before Presentation)

Open two terminal tabs on Windows:

### Terminal 1: Ollama Service
```powershell
$env:OLLAMA_MODELS = "E:\Downloads\.ollama\models"
ollama serve
```
*Verify ready: `curl.exe -s http://localhost:11434/api/tags` returns `qwen2.5:3b`.*

### Terminal 2: SentinelAI Launcher
```powershell
.\scripts\start_sentinelai.ps1
```
*Verify ready:*
- Streamlit Dashboard: [http://localhost:8501](http://localhost:8501)
- FastAPI Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- AI Status: [http://localhost:8000/api/ai/status](http://localhost:8000/api/ai/status)

---

## 5–7 Minute Demonstration Script

### Step 1: Introduction & Problem Statement (0:00 – 0:45)
- **Speaker Script**:
  > *"Modern cloud and on-premise infrastructure generates thousands of raw telemetry metrics per minute. When servers experience memory leaks, runaway compute loops, or I/O saturation, operations teams face alert fatigue. Rule-based thresholds either miss subtle multivariate anomalies or trigger noisy false alarms. Furthermore, generic LLM assistants hallucinate dangerous remediation commands or try to kill critical operating system processes.*
  >
  > *SentinelAI solves this by combining three layers: (1) real-time OS telemetry collection, (2) an unsupervised 39-feature Isolation Forest ML engine for calibrated anomaly scoring, and (3) an evidence-grounded AI diagnostic engine backed by strict OS safety filters and instant deterministic fallback."*

---

### Step 2: Dashboard Overview & Live Telemetry (0:45 – 1:30)
- **Action**: Navigate to [http://localhost:8501](http://localhost:8501) in your browser.
- **Showcase**:
  1. **Top Banner**: Point to the operational status badge, active ML engine (`IsolationForestDetector`), and SQLite persistence count.
  2. **Sidebar**: Point out the **Runtime & Storage Engine** block showing `ML Engine: IsolationForestDetector` and `AI Engine: qwen2.5:3b (🟢 Enabled)`.
  3. **Section 1 (System Overview)**: Highlight the 5 metric cards (CPU, RAM, Disk, Network, Top Processes) and the real-time resource saturation Plotly bar chart.
  4. **Section 2 (Health & Risk Analysis)**: Navigate to the `🛡️ Health & Risk Analysis` tab. Show the circular gauges for **Overall Health Score** (0–100) and **Calibrated Anomaly Score**, along with the **Five-Tier Risk Categorization Matrix** (Normal, Low, Moderate, High, Critical).

---

### Step 3: Safe Deterministic Anomaly Simulation (1:30 – 2:30)
- **Action**: Click on `🧪 Anomaly Simulation` in the sidebar.
- **Explanation**:
  > *"Rather than injecting risky hardware faults or stressing physical disks during a live review, SentinelAI includes a built-in deterministic simulation lab. It generates physically valid mathematical telemetry vectors and runs them through our full 39-feature pipeline."*
- **Action**:
  1. Leave Scenario set to **`CPU Thread Runaway / Spike`** (or select **`Memory Leak / Exhaustion`**).
  2. Click **🚀 Run Anomaly Simulation**.
- **Observation**:
  - Point to the **Execution Assessment Banner**: `🔴 ANOMALOUS OUTLIER DETECTED`.
  - Show the comparative bar chart: Baseline vs. Simulated telemetry (+78% CPU increase).
  - Show the ML evaluation: Health Score drops (e.g. from 95 to 46.8), Anomaly Score spikes, and Risk Tier elevates to `🔴 Critical Risk`.

---

### Step 4: AI Incident Diagnosis & Runbook (2:30 – 4:00)
- **Action**: Scroll down to **Section 4: SentinelAI Incident Runbook & Diagnosis**.
- **Transparency Note on CPU Latency**:
  > *"Because we run an open-weight 3-billion-parameter LLM locally on an Intel CPU with zero external cloud dependencies or API costs, inference takes approximately 45–60 seconds."*
- **Choose Demo Path**:
  - **Path A (Live LLM Generation)**:
    1. Click **🧠 Generate AI Diagnosis for Scenario**.
    2. While the spinner is active, explain that SentinelAI synthesizes top processes, multivariate feature vectors, and ML predictions into a structured JSON schema.
    3. Once rendered, inspect the generated report.
  - **Path B (Fast 1-Second Fallback Demonstration)**:
    If running short on time, proceed directly to Step 5 to demonstrate the instant deterministic fallback engine!
- **Key Elements to Highlight in the Report**:
  - **Incident Summary**: Contextual summary of the simulated event.
  - **Evidence-Based Causes**: Ranked hypotheses with supporting metrics (`HIGH CONFIDENCE`).
  - **Prioritized Investigation Steps**: Concrete diagnostics tailored to the host OS.
  - **Advisory Runbook & Guardrails**: Point to the **⚠️ Mandatory Operator Review Required** warning banner:
    > *"Notice that autonomous command execution is permanently disabled. SentinelAI treats all model output as untrusted advice, validates commands against the active OS, and requires human operator sign-off before execution."*

---

### Step 5: Deterministic Fallback During Outages (4:00 – 5:00)
- **Speaker Script**:
  > *"What happens if the Ollama daemon crashes, runs out of memory, or exceeds timeout in a critical production outage? SentinelAI never fails open or drops observability."*
- **Action**:
  1. Open Terminal 1 (where `ollama serve` is running) and press `Ctrl+C` (or in PowerShell run `Stop-Process -Name "ollama*" -Force`).
  2. Switch to browser or terminal.
  3. In Terminal 2, run a diagnosis via the REST API:
     ```powershell
     Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ai/diagnose" -Method Post -Body '{}' -ContentType "application/json"
     ```
- **Observation**:
  - Request completes in **under 3 seconds** (`latency_ms: ~3000ms`).
  - Response returns:
    - `"is_fallback": true`
    - `"model_used": "heuristic_fallback"`
    - `"fallback_reason": "Cannot connect to Ollama daemon..."`
    - `"health_score": 56.6` (authoritative ML score remains perfectly preserved!)
  - The dashboard displays the amber **DETERMINISTIC FALLBACK** badge with verified safe investigation steps.

---

### Step 6: Service Restoration & API Architecture (5:00 – 6:00)
- **Action**:
  1. Restart Ollama in Terminal 1:
     ```powershell
     $env:OLLAMA_MODELS = "E:\Downloads\.ollama\models"; ollama serve
     ```
  2. Open FastAPI Swagger documentation in browser: [http://localhost:8000/docs](http://localhost:8000/docs).
  3. Show the clean OpenAPI schema:
     - `POST /api/ai/diagnose` — Generates on-demand incident runbooks.
     - `GET /api/ai/status` — Real-time probe of Ollama reachability and fallback status.
     - `GET /healthz` — Liveness check.
     - `POST /api/simulation/run` — Headless simulation endpoint for automated testing.

---

### Step 7: Test Evidence & Conclusion (6:00 – 7:00)
- **Key Evidence to Present**:
  - **Full Test Suite**: 344 automated tests (334 core unit/integration/ML/API tests + 10 Playwright E2E browser tests).
  - **Safety Filter**: Prohibits termination of Windows System Idle Process (PID 0), critical OS processes, and destructive commands (`rm -rf`, `format`, `taskkill /IM *`).
  - **No Hardware Stress**: Zero destructive CPU or disk burning during testing.
- **Closing**:
  > *"SentinelAI delivers actionable, explainable server health monitoring with defense-in-depth safety, verified ML intelligence, and rock-solid local fallback. Thank you!"*

---

## Post-Demo Cleanup
To shut down SentinelAI services cleanly:
```powershell
.\scripts\stop_sentinelai.ps1
```
