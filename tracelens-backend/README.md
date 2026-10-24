# TraceLens backend

## Configure

From this directory, copy `.env.example` to `.env` and set `MONGODB_URI` and `MONGODB_DATABASE`. Never commit `.env`.

Local MongoDB: from the repository root run `docker compose up -d mongodb`; use `mongodb://localhost:27017`.

Atlas: copy the `mongodb+srv://...` URI from Atlas → Connect → Drivers. Use a database user (not your Atlas website login), URL-encode special characters in username/password, and allow your current public IP under Network Access. Do not disable TLS verification. A TCP connection alone does not prove the TLS or MongoDB connection works.

## Run (PowerShell)

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env before continuing if using Atlas
python test_mongo.py
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/health`. Startup performs a MongoDB ping and index creation; the service fails to start if MongoDB is unreachable. Health returns HTTP 503 if database readiness is lost.

## Atlas TLS troubleshooting

1. Run `nslookup -type=SRV _mongodb._tcp.<cluster-host>`.
2. Run `Test-NetConnection <shard-host> -Port 27017`.
3. Test `python test_mongo.py` and compare using a mobile hotspot.
4. If TCP succeeds but TLS fails, investigate VPN/proxy, antivirus HTTPS inspection, firewall, corporate/campus network policies, Python/OpenSSL, and the exact Atlas URI. Do not set `tlsAllowInvalidCertificates` or disable certificate verification.

## API

Endpoints include `/health`, `/api/projects`, `/api/runs`, `/api/runs/{run_id}`, `/api/runs/{run_id}/events`, `/api/runs/compare`, and `/api/runs/{run_id}/findings`.


## Incident memory

The backend stores redacted, project-scoped incident summaries and evidence references when investigations identify failed runs. `GET /api/projects/{project_id}/memories` lists these records. `POST /api/memories/{memory_id}/confirm-fix` can record an explicitly confirmed corrective action. The run-level chatbot API has been removed; investigation reports and structured run/event APIs remain available.

Memory matching is deterministic and does not require a separate vector database. Similarity is a lead for investigation, not proof of shared causation. See the repository-root `MONGODB_AI_DIRECTION_AND_TEST_MATRIX.md` for MongoDB recommendations and expanded test coverage.
