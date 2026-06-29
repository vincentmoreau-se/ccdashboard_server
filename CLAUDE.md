# CCDashboard Server

Serveur centralisé qui **ingère la télémétrie Claude Code** des clients
[`ccdashboard`](../ccdashboard) et l'affiche sur un dashboard « flight-deck »
protégé par mot de passe (live + historique). Cible : monitorer un hackathon
(~30 projets / 300 participants).

- **Backend** (`backend/`) : Python 3.11+ · FastAPI · SQLite · géré par `uv`
- **Frontend** (`frontend/`) : React 18 · Vite · Tailwind · TanStack Query
- Voir `backend/CLAUDE.md` et `frontend/CLAUDE.md` pour les conventions locales.

## Architecture

```
client ccdashboard ──POST /ingest (Bearer token)──► FastAPI ──► SQLite
                                                       │
navigateur ──login (cookie de session)──► REST + SSE ◄─┘
```

## Invariants à respecter

- **Ingest idempotent** : `POST /ingest` (payload `schema_version:1`) fait un
  **UPSERT** clé `source::session_id`. La livraison client est *at-least-once* et
  renvoie des sessions entières → on **écrase** l'état, jamais d'incrément.
- **Enrichissement au query-time** : un CSV `user_id,team_id,localisation[,display_name]`
  est joint à la lecture. Les `user_id` inconnus → bucket `UNKNOWN`, jamais rejetés.
  Rechargeable à chaud via `POST /api/admin/participants`.
- **Live par différence de snapshots** : une tâche de fond agrège un snapshot toutes
  les `snapshot_interval_seconds` ; les débits (tokens/min, coût/h) se calculent
  par delta entre snapshots (immunisé contre les renvois). Session « live » =
  `is_active=1` **et** vue depuis < `live_window_seconds` (**horloge serveur** uniquement).
- **« tokens » = `in_tokens + out_tokens`** partout. Les tokens de cache sont
  exposés séparément (`cache_*`, `cache_efficiency`), jamais additionnés au total.

## Commandes

```bash
# Backend (port 8090)
cd backend && uv sync && uv run uvicorn app.main:app --port 8090 --reload
cd backend && uv run pytest                         # tests API

# Frontend (port 5180, proxy /api + /ingest -> :8090)
cd frontend && npm install && npm run dev -- --port 5180 --strictPort
cd frontend && npx playwright test                  # E2E (backend + Vite doivent tourner)
```

Ports choisis pour ne pas entrer en conflit avec le client `ccdashboard` local
(8000 / 5173).

## Configuration

Toute la config passe par des variables d'environnement préfixées **`CCSRV_*`**
(défauts dans `backend/app/config.py`, exemples dans `.env.deploy.example` et
`backend/.env.example`). Secrets clés : `CCSRV_INGEST_TOKEN`,
`CCSRV_DASHBOARD_PASSWORD`, `CCSRV_SECRET_KEY`.

## Déploiement

`Dockerfile` multi-stage (build du SPA → servi par FastAPI) + `docker-compose.yml`.
Détails et historique : `DEPLOYMENT.local.md`. Déployé sur `msfserver.fr/ccdash`
(sous-chemin) — build avec `VITE_BASE=/ccdash/` + `VITE_API_BASE=/ccdash`, et
`CCSRV_COOKIE_SECURE=true` derrière le reverse-proxy TLS.
