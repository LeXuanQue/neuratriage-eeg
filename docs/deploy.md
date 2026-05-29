# Deploy NeuraTriage EEG

The active app is a **single FastAPI process** that serves both the REST/WebSocket
API and the static frontend on one port (`8501`). Deploy it as a Docker container
on a host that runs long-lived processes: **Render, Railway, Fly.io, or a VPS**.
`vercel.json` is only for a static frontend preview — it does **not** deploy the
FastAPI/ML backend.

## ⚠️ Architecture constraints (read first)

- **One worker / one replica.** `ModelManager`, `SessionManager` and the in-memory
  rate limiter are per-process singletons, and live WebSocket detector state lives
  in RAM. Multiple workers/replicas would not share them, and SQLite would contend
  on writes. Scale **vertically** (bigger instance), never by worker count.
  The Dockerfile already pins `--workers 1`.
- **Stateful disk.** SQLite (`data/neuratriage.db`), uploads (`data/uploads/`) and
  PDFs (`data/reports/`) live under `data/`. Mount a persistent volume at `/app/data`
  or the data resets on every redeploy.

## 1. Secrets / environment

Copy `.env.example` → `.env` and set at minimum:

```env
APP_ENV=production
JWT_SECRET=<64-char random>      # python -c "import secrets; print(secrets.token_urlsafe(64))"
ALLOWED_ORIGINS=https://your-domain.example      # comma-separated, your real origin(s)
```

With `APP_ENV=production` the app **refuses to boot** unless `JWT_SECRET` is strong
(not the dev default, >= 32 chars), and it emits HSTS + a CSP response header.

Optional weekly-report email (otherwise PDFs are generated but not emailed):

```env
SENDGRID_API_KEY=SG.xxxx
SENDGRID_FROM_EMAIL=reports@your-verified-sender   # must be a SendGrid-verified sender/domain
SENDGRID_FROM_NAME=NeuraTriage EEG
```

## 2. Model + datasets in the image

- The demo model (`backend/models/model.joblib`) is baked into the image.
  Auto-loaded on startup; SHA-256 logged for integrity.
- `results/*.json` is baked in so the **Insights** screen has research metrics.
- `dataset_hemorrhagic/` (4 small NPZ) is baked in, so HS replay works out of the box.
- The **large** replay sets (`dataset_ischemic`, `dataset_healthy`, `dataset_npz`)
  are `.dockerignore`d to keep the image small. To enable IS/NS replay:
  - **docker-compose:** already mounted read-only (see `docker-compose.yml`), or
  - **hostless (Render/Fly):** remove them from `.dockerignore` to bake a curated
    subset in, or attach a volume and copy them in.

## 3. Run

### docker-compose (VPS / local prod)
```bash
cp .env.example .env        # then edit: APP_ENV=production, JWT_SECRET, ALLOWED_ORIGINS
docker compose up --build -d
curl http://127.0.0.1:8501/api/health
```

### Render / Railway / Fly.io
- Build from the `Dockerfile` (repo root). Port `8501`.
- Set env vars from step 1 in the dashboard (do **not** commit `.env`).
- Attach a persistent disk mounted at `/app/data`.
- Keep instance count = 1.
- Health check path: `/api/health`.

## 4. Post-deploy smoke check

```bash
curl -s https://your-domain/api/health
# login (demo users still exist — change/remove before real use):
curl -s -X POST https://your-domain/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"doctor@neuratriage.com","password":"demo1234"}'
```

Then open `https://your-domain/` -> log in -> **Insights** should show metrics, and
**Setup -> Replay** should list ischemic + healthy + hemorrhagic cases.

## 5. Still-open hardening (not blocking a demo)

- Demo users are hardcoded in `backend/app/auth.py` — replace with a real user store
  before any non-demo use.
- Frontend uses in-browser Babel + CDN React (dev builds). A build step (esbuild/Vite)
  would let the CSP drop `unsafe-eval`/`unsafe-inline` and cut load time.
- Emergency-contact editing is add/delete only (no PUT endpoint).
