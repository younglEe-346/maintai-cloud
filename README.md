# MaintAI Cloud — Predictive Maintenance SaaS Platform

An end-to-end industrial IoT predictive maintenance system powered by FastAPI, PostgreSQL, Redis, Celery, and Streamlit.

## Quick Start Guide

### 1. Launch Backend (Docker Compose)
Ensure Docker Desktop is open and run:
```bash
docker-compose up --build -d
```

### 2. Setup Virtual Environment & Install Frontend Dependencies
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Run Streamlit Dashboard
```bash
streamlit run app_frontend.py
```

### 4. Run Telemetry Simulator
In a separate terminal tab:
```bash
python -m simulator.stream_simulator
```
