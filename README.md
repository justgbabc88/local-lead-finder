# LocalLeadEngine

A full-stack B2B lead scraping and outreach platform. Scrapes Google Maps for local
businesses at scale, enriches leads via Apollo and CompanyEnrich, validates emails,
and pushes contacts to Email Bison campaigns.

## Structure

```
localleadengine/
├── frontend/          # React + Vite + Tailwind (Vercel)
├── backend/           # FastAPI (Railway API + worker services)
├── supabase/
│   └── migrations/    # SQL migration files (numbered)
├── railway.toml       # Railway service definitions
└── README.md
```

## Tech Stack

| Layer            | Technology                                    |
| ---------------- | --------------------------------------------- |
| Frontend         | React + Vite + TypeScript + Tailwind CSS      |
| Backend API      | FastAPI (Python 3.11+)                        |
| Database         | Supabase (PostgreSQL)                         |
| Realtime         | Supabase Realtime                             |
| Job Queue        | Redis + RQ (Phase 2+)                         |
| Scraping API     | Google Places API (v1)                        |
| Enrichment       | Apollo.io + CompanyEnrich (Phase 3+)          |
| Validation       | Pluggable (NeverBounce / ZeroBounce / etc.)   |
| Outreach         | Email Bison (Phase 5+)                        |
| Auth             | Supabase Auth                                 |

## Build Phases

1. **Phase 1 — Core Scraper** (current): sync scraping, single API key, lead table UI
2. **Phase 2** — Parallel Railway workers + API key pool + Supabase Realtime
3. **Phase 3** — Manual Apollo / CompanyEnrich enrichment
4. **Phase 4** — Pluggable email validation
5. **Phase 5** — Email Bison integration (push + analytics)
6. **Phase 6** — AI personalization, lead scoring, templates, suppression, scheduling, etc.

Bonus: **Domain Health Monitor** (SPF/DKIM/DMARC/blacklist dashboard).

## Local Dev — Phase 1

### Prerequisites

- Python 3.11+
- Node 20+ and pnpm (or npm)
- A Supabase project
- A Google Places (v1) API key

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in values
npm run dev
```

### Database

Run the SQL files in `supabase/migrations/` in order against your Supabase project
(via the SQL editor or the Supabase CLI).

### Seeding US zip codes

Once the DB schema is in place, run:

```bash
cd backend
python -m app.db.seed_zips
```

This loads the ~42k US zip codes from the GeoNames dataset (downloaded on first run)
into `us_zip_codes`.
