# LocalLeadEngine — Setup Walkthrough

This document captures everything needed to take the repo from a fresh clone to a
working Phase 1 instance, plus the optional services for later phases.

The repo has already been bootstrapped on this machine: a Python venv with all
backend deps is at `backend/.venv`, frontend `node_modules` is installed, and
placeholder `.env` files exist (gitignored). Both dev servers have been verified
to boot. Replace the `REPLACE_ME` values in the env files with real credentials
to actually use the app.

---

## What you must do manually (Phase 1)

These require accounts/keys that only you can create.

### 1. Create a Supabase project
1. Sign up at https://supabase.com and create a new project.
2. Open **Project Settings → API** and copy:
   - `Project URL` → `SUPABASE_URL` and `VITE_SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY` and `VITE_SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_KEY` (server-only, never ship to client)
   - `JWT Secret` → `SUPABASE_JWT_SECRET`

### 2. Run the SQL migrations
In the Supabase **SQL Editor**, paste and run each file in `supabase/migrations/`
in order (0001 → 0009). They are safe to run once each.

### 3. Seed US zip codes
With `backend/.env` filled in:
```
cd backend
.venv/bin/python -m app.db.seed_zips
```
Downloads ~42k rows from GeoNames into `us_zip_codes` (idempotent upsert).

### 4. Get a Google Places (v1) API key
1. Open https://console.cloud.google.com, create a project.
2. Enable **"Places API (New)"**.
3. Create an API key, restrict it to the Places API.
4. Put it in `GOOGLE_PLACES_API_KEY` (Phase 1 fallback). Phase 2+ uses a
   per-workspace pool stored in the `api_keys_google` table.

### 5. Update `.mcp.json` (optional)
If you want the Supabase MCP server in Claude Code, edit `.mcp.json` and replace
`YOUR_PROJECT_REF` with your Supabase project ref, then export
`SUPABASE_ACCESS_TOKEN` in your shell.

---

## Run locally

Backend (FastAPI):
```
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (Vite):
```
cd frontend
npm run dev
```

The frontend is at http://localhost:5173 and talks to the backend at
http://localhost:8000 (override with `VITE_API_URL`).

---

## Optional services (Phase 2+)

All workspace-scoped API keys are entered through the Settings page in the app
and stored in the `workspace_settings` table — not in `.env`.

| Phase | Service | What you need |
|-------|---------|---------------|
| 2 | Redis (managed or self-hosted) | `REDIS_URL` in backend `.env`; uncomment worker services in `railway.toml`. |
| 3 | [Apollo.io](https://www.apollo.io) | API key → workspace settings (org enrichment + contact discovery). |
| 3 | [CompanyEnrich](https://www.enrich.co) | API key → workspace settings (alternate enrichment). |
| 4 | NeverBounce / ZeroBounce / MillionVerifier / Reoon | Pick at least one validator; API key → workspace settings; choose default in settings. |
| 5 | [Email Bison](https://emailbison.com) (self-hosted) | Base URL + API key → workspace settings; configure mailboxes + campaigns inside Bison. |
| 6 | [Anthropic API](https://console.anthropic.com) | API key → workspace settings (AI cold-email opener generation). |
| Bonus | [MxToolbox API](https://mxtoolbox.com/api) | Optional API key → workspace settings; without it, Domain Health uses 5 free DNS RBLs instead of 100+. |
| Bonus | Slack incoming webhook | Webhook URL → workspace settings (job + domain alerts). |

### Phase 2 worker processes

Once Redis is up, run the workers and scheduler in separate processes:
```
cd backend
.venv/bin/rq worker scrape_tasks --url $REDIS_URL --worker-ttl 1200
.venv/bin/rq worker enrichment_tasks --url $REDIS_URL --worker-ttl 1200
.venv/bin/python -m app.workers.scheduler && .venv/bin/rqscheduler --url $REDIS_URL -i 60
```

---

## Deployment

### Railway (backend + workers)
`railway.toml` defines five services: `api`, `redis`, `scrape-worker` (10
replicas), `enrichment-worker` (2 replicas), `scheduler` (1 replica). Set every
backend `.env` variable as a Railway project variable.

### Vercel (frontend)
`frontend/vercel.json` is present. Set `VITE_SUPABASE_URL`,
`VITE_SUPABASE_ANON_KEY`, `VITE_API_URL` as Vercel env vars; build command is
`npm run build`, output dir is `dist/`.

After deploy, add the Vercel URL (and any preview-deploy regex) to backend
`CORS_ORIGINS` / `CORS_ORIGIN_REGEX`.

---

## Security note

`supabase/migrations/0002_api_keys_jobs_settings.sql` stores workspace API keys
in plaintext. Before going to production, switch them to Supabase Vault
encryption (or another KMS) — they currently sit in a regular table column.
