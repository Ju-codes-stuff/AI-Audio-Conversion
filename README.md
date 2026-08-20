# 🏛️ GrievanceAI — Unified Multilingual Government Grievance Platform

> File government grievances in any of 22 Indian languages using AI-powered speech recognition and translation.

---

## 📋 Table of Contents

- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [First-Time Setup](#first-time-setup)
- [Starting the Platform](#starting-the-platform)
- [Stopping Everything](#stopping-everything)
- [URLs at a Glance](#urls-at-a-glance)
- [Testing the Full Flow](#testing-the-full-flow)
- [Troubleshooting](#troubleshooting)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 + React (TypeScript) |
| Backend API | Python + FastAPI |
| Async Workers | Celery + Redis |
| Database | PostgreSQL 18 |
| Object Storage | MinIO (S3-compatible) |
| AI — Speech-to-Text | AI4Bharat IndicASR (mock in dev) |
| AI — Translation | AI4Bharat IndicTrans2 (mock in dev) |
| AI — Classification | LLM / NLP (mock in dev) |
| Audio Processing | FFmpeg |

---

## Prerequisites

Install these once before anything else:

| Tool | Download | Notes |
|------|----------|-------|
| **Python 3.11+** | https://www.python.org/downloads/ | Check "Add to PATH" during install |
| **Node.js 18+** | https://nodejs.org/ | Includes npm |
| **PostgreSQL 18** | https://www.postgresql.org/download/windows/ | Remember the `postgres` password you set |
| **Redis** | https://github.com/tporadowski/redis/releases | Download the `.msi` installer — runs as a Windows Service |
| **FFmpeg** | Run: `winget install --id Gyan.FFmpeg -e` | Restart PowerShell after installing |

> **Verify everything is installed** by opening a new PowerShell window and running:
> ```powershell
> python --version    # Python 3.11.x
> node --version      # v18.x or higher
> ffmpeg -version     # ffmpeg version ...
> ```

---

## Project Structure

```
D:\New\
├── backend/        ← FastAPI Python backend
└── frontend/       ← Next.js React frontend
```

---

## First-Time Setup

> ⚠️ **Do this only once.** After setup, go directly to [Starting the Platform](#starting-the-platform).

### Step 1 — Create the PostgreSQL database

Open **Start Menu** → search **"SQL Shell (psql)"** → open it.

Press **Enter** for every prompt until you see the password prompt, then type your `postgres` password:

```
Server [localhost]:        ← Enter
Database [postgres]:       ← Enter
Port [5432]:               ← Enter
Username [postgres]:       ← Enter
Password for user postgres: ← type your password
```

Once inside (you see `postgres=#`), paste these commands:

```sql
CREATE USER grievance WITH PASSWORD 'grievance';
CREATE DATABASE grievance_db OWNER grievance;
GRANT ALL PRIVILEGES ON DATABASE grievance_db TO grievance;
\q
```

---

### Step 2 — Set up the Backend

Open **PowerShell** and run:

```powershell
# Navigate to backend
cd D:\New\backend

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install all Python dependencies
pip install -r requirements.txt

# Copy the environment config file
copy .env.example .env
```

Open `.env` in Notepad and set a proper `SECRET_KEY`:

```powershell
notepad .env
```

Change this line:
```
SECRET_KEY=CHANGE_ME_TO_A_LONG_RANDOM_SECRET
```
To something like:
```
SECRET_KEY=my-super-secret-key-at-least-32-characters-long
```
Save and close.

---

### Step 3 — Run database migrations

```powershell
# Still in D:\New\backend with .venv active
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial database schema
```

---

### Step 4 — Set up the Frontend

Open a **new PowerShell window**:

```powershell
cd D:\New\frontend
npm install
```

---

## Starting the Platform

Every time you want to run the project, open **4 PowerShell windows** and run one command in each.

---

### Window 1 — Backend API Server

```powershell
cd D:\New\backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

✅ Ready when you see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### Window 2 — Celery Worker (AI Pipeline)

```powershell
cd D:\New\backend
.venv\Scripts\activate
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

> ⚠️ `--pool=solo` is **required on Windows**. The default pool doesn't work on Windows.

✅ Ready when you see:
```
[celery@...] ready.
```

---

### Window 3 — Frontend

```powershell
cd D:\New\frontend
npm run dev
```

✅ Ready when you see:
```
✓ Ready in ~3s
- Local: http://localhost:3000
```

---

### Window 4 — (Optional) Celery Flower — Worker Monitor

```powershell
cd D:\New\backend
.venv\Scripts\activate
celery -A app.workers.celery_app flower --port=5555
```

---

## Stopping Everything

Press `Ctrl + C` in each PowerShell window.

To stop Redis (if needed):
```powershell
# Run as Administrator
Stop-Service Redis
```

---

## URLs at a Glance

| Service | URL | Notes |
|---------|-----|-------|
| 🌐 **Website** | http://localhost:3000 | Main citizen-facing app |
| 📖 **API Docs (Swagger)** | http://localhost:8000/api/v1/docs | Interactive API testing |
| ❤️ **Health Check** | http://localhost:8000/health | Verify backend is up |
| 🌸 **Flower (Workers)** | http://localhost:5555 | Monitor Celery tasks |

---

## Testing the Full Flow

1. Open http://localhost:3000
2. Click **Register** → create an account (phone number or email)
3. Click **File a Grievance** (or the 🎤 button in the navbar)
4. **Select a language** (e.g. Hindi — हिन्दी)
5. Click the 🎤 mic button → speak your grievance → click ⏹ to stop
6. Click **Upload & Process** → watch the AI pipeline (ASR → Translation → Classification)
7. On the Review page — check the AI output, edit any fields, click **Confirm & Submit**
8. You'll receive a **GRV-YYYY-NNNNNN** reference ID 🎉
9. Go to **Track** → enter your GRV ID → see status

---

## Troubleshooting

### `alembic upgrade head` fails with password error
The `grievance` PostgreSQL user doesn't exist. Re-run the SQL commands in Step 1.

### `redis-cli` not found / Redis errors
Redis may not be running. Open PowerShell **as Administrator** and run:
```powershell
Start-Service Redis
```

### `ffmpeg` not found
Close and reopen PowerShell after installing FFmpeg. If still not found:
```powershell
winget install --id Gyan.FFmpeg -e
```

### Celery worker crashes on Windows
Make sure you're using `--pool=solo`:
```powershell
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

### Frontend can't reach backend (CORS / network error)
Ensure the backend is running on port 8000. Check `D:\New\frontend\.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Audio upload fails (storage error)
MinIO is not running. For local development, the mock AI pipeline doesn't strictly need object storage — but if you see storage errors, start MinIO:

Download from https://min.io/download#/windows, then run:
```powershell
minio.exe server D:\minio-data --console-address :9001
```

---

## Environment Variables

All backend config lives in `D:\New\backend\.env`.
Key settings for local development (already set in `.env.example`):

```env
ASR_USE_MOCK=true           # Use mock speech-to-text (no model needed)
TRANSLATION_USE_MOCK=true   # Use mock translation (no model needed)
LLM_USE_MOCK=true           # Use mock AI classifier (no model needed)
```

> When you're ready to use real AI models, set these to `false` and configure
> `ASR_SERVICE_URL`, `TRANSLATION_SERVICE_URL` to point to your IndicASR/IndicTrans2 instances.

---

*Built with ❤️ for every citizen of India.*
