# TraceLens — RAG Observability & Diagnostics

TraceLens captures RAG execution traces, detects common failures, compares runs, and investigates failures against prior successful executions.

## Repository layout

```text
TraceLens/
├── tracelens-backend/       # FastAPI API, MongoDB persistence, OAuth
│   ├── app/
│   │   ├── auth.py          # Google/GitHub OAuth and user sessions
│   │   ├── main.py          # API routes and workspace authorization
│   │   ├── models.py        # Request/response validation
│   │   ├── diagnostics.py   # Deterministic issue detection
│   │   └── investigation.py # Historical investigation
│   ├── requirements.txt
│   └── tests/
├── tracelens-frontend/      # React + TypeScript + Vite dashboard
├── tracelens-sdk/           # Python SDK and CLI
├── rag-customer-support/    # Example LangChain RAG app
├── docker-compose.yml       # MongoDB for local development
├── .env.example             # Configuration template; never store secrets here
└── FAILURE-CAPTURE-AND-INVESTIGATION.md
```

## Local development

Prerequisites: Python 3.11+, Node.js 20+, and Docker Desktop (or a local MongoDB instance).

1. Copy `.env.example` to `tracelens-backend/.env` or load the variables into your shell. Keep real credentials out of Git.
2. Start MongoDB from the repository root:

   ```powershell
   docker compose up -d mongodb
   ```

3. Start the backend:

   ```powershell
   cd tracelens-backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. In a second terminal, start the frontend:

   ```powershell
   cd tracelens-frontend
   npm install
   npm run dev
   ```

5. Open `http://127.0.0.1:5173`. The API health endpoint is `http://127.0.0.1:8000/health`; interactive API docs are at `http://127.0.0.1:8000/docs`.

## Authentication and per-user projects

The default `AUTH_MODE=local` is for local development and hackathon demos. It is **not** an authenticated multi-user deployment.

To enable Google and/or GitHub OAuth:

1. Register an OAuth application with the provider.
2. Set `AUTH_MODE=oauth`.
3. Set a long random `AUTH_SECRET_KEY` (at least 32 random bytes).
4. Set the provider client ID and secret in the backend environment.
5. Set `FRONTEND_ORIGIN` to the exact frontend origin. Set `COOKIE_SECURE=true` when using HTTPS.
6. Register the callback URL at the provider:
   - Google: `https://YOUR_API_HOST/api/auth/callback/google`
   - GitHub: `https://YOUR_API_HOST/api/auth/callback/github`
7. Deploy behind HTTPS and configure CORS to the exact frontend origin.

Auth endpoints:
- `GET /api/auth/status` — enabled providers
- `GET /api/auth/me` — current signed-in identity
- `GET /api/auth/login/google` or `/api/auth/login/github` — begin provider flow
- `GET /api/auth/callback/{provider}` — provider callback
- `POST /api/auth/logout` — clear the session

OAuth users are stored by provider + stable provider subject, and projects created by the web app are assigned to that user. OAuth uses a signed HttpOnly session cookie; provider secrets remain on the server.

**Important integration boundary:** the SDK currently uses the project/run API directly and does not yet implement per-project ingestion API keys. OAuth-mode API authorization is intended for authenticated dashboard access; configure and test an SDK service-auth/API-key flow before using OAuth mode for remote developer SDK ingestion. Do not describe this build as fully production-hardened until that flow, provider callback configuration, TLS deployment, rate limits, CSRF policy, and end-to-end tenant-isolation tests have been validated.

## Test commands

Backend:
```powershell
cd tracelens-backend
python -m pip install -r requirements.txt
python -m pytest
```

SDK:
```powershell
cd tracelens-sdk
python -m pip install -e ".[dev,langchain]"
python -m pytest
```

Frontend:
```powershell
cd tracelens-frontend
npm ci
npm test
npm run build
```

## Security checklist before public submission

- [ ] Use a strong `AUTH_SECRET_KEY`; never use the example value.
- [ ] Enable HTTPS and `COOKIE_SECURE=true` in deployed OAuth environments.
- [ ] Configure OAuth callback URLs to exact deployed API hostnames.
- [ ] Restrict CORS to the deployed frontend origin.
- [ ] Keep `.env`, OAuth secrets, database credentials, and production data out of Git.
- [ ] Configure MongoDB authentication, network restrictions, backups, and least-privilege access.
- [ ] Implement project-scoped SDK ingestion API keys before enabling remote SDK ingestion in OAuth mode.
- [ ] Run provider-specific login/logout tests and cross-user access-control tests against a non-production database.
