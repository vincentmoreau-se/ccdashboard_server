# CCDashboard Server

Serveur centralisé qui **ingère la télémétrie Claude Code** envoyée par les
clients [`ccdashboard`](../ccdashboard) et l'affiche sur un **dashboard
« flight-deck » protégé par mot de passe** — métriques **live** et
**historiques**. Conçu pour monitorer un hackathon (30 projets / 300 participants).

- **Backend** : Python + FastAPI + SQLite (géré par `uv`)
- **Frontend** : React + Vite + Tailwind (esthétique mission-control)
- **Tests** : pytest (API) + Playwright (E2E navigateur)

## Architecture

```
client ccdashboard  ──POST /ingest (Bearer token)──►  FastAPI  ──►  SQLite
                                                          │
navigateur  ──login (cookie de session)──►  REST + SSE  ◄─┘
```

- **Ingest** : `POST /ingest`, en-tête `Authorization: Bearer <token>`, payload
  `schema_version:1`. **UPSERT idempotent** (clé `source::session_id`) — la
  livraison at-least-once du client renvoie des sessions entières, le serveur
  écrase l'état (jamais d'incrément).
- **Enrichissement** : un CSV `user_id,team_id,localisation[,display_name]` est
  joint au query-time → leaderboards par équipe. Les `user_id` inconnus tombent
  dans le bucket `UNKNOWN` (jamais rejetés). Rechargeable à chaud via
  `POST /api/admin/participants`.
- **Live** : une tâche de fond écrit des snapshots agrégés toutes les 60s ;
  les débits (tokens/min, coût/h) sont calculés par différence entre snapshots
  (immunisé contre les renvois). Une session est « live » si
  `is_active=1` ET vue depuis moins de `live_window_seconds` (horloge serveur).

## Démarrage local

### Backend
```bash
cd backend
cp .env.example .env          # ajuster CCSRV_INGEST_TOKEN + CCSRV_DASHBOARD_PASSWORD
# placer participants.csv (colonnes: user_id,team_id,localisation,display_name)
uv sync
uv run uvicorn app.main:app --port 8090 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev -- --port 5180 --strictPort   # proxy /api -> http://localhost:8090
```
Ouvrir http://localhost:5180 — se connecter avec `CCSRV_DASHBOARD_PASSWORD`.

> Le proxy Vite (`vite.config.ts`) pointe vers `http://localhost:8090`. En dev
> tout est same-origin pour que le cookie de session circule (y compris au SSE).

## Configurer un client ccdashboard pour exporter ici
Côté client (`backend/.env` de ccdashboard) :
```
CCDASH_EXPORT_ENABLED=true
CCDASH_EXPORT_ENDPOINT=http://localhost:8090/ingest
CCDASH_EXPORT_TOKEN=<même valeur que CCSRV_INGEST_TOKEN>
CCDASH_EXPORT_USER_ID=<email/identifiant du participant, doit matcher le CSV>
CCDASH_EXPORT_INTERVAL_MINUTES=1     # ~live
```

## Tests
```bash
cd backend  && uv run pytest                 # 31 tests API
cd frontend && npx playwright install chromium && npx playwright test   # 7 E2E
```
Les E2E supposent le backend (8090, seedé) et Vite (5180) déjà démarrés.

## Endpoints principaux
| Méthode | Route | Auth |
|---|---|---|
| POST | `/ingest` | Bearer ingest |
| POST | `/api/login` · `/api/logout` · GET `/api/me` | — / cookie |
| GET | `/api/overview` `/api/timeseries` `/api/leaderboard/{teams,participants}` `/api/teams/{id}` `/api/models` `/api/providers` `/api/tools` `/api/sessions` | cookie |
| GET | `/api/live/snapshot` · `/api/live/stream` (SSE) | cookie |
| POST | `/api/admin/participants` · GET `/api/admin/participants/unknown` | cookie |

## Déploiement
Conteneurisé via le `Dockerfile` multi-stage (build frontend → servi par
FastAPI) + `docker-compose.yml`. Derrière un reverse-proxy TLS : poser
`CCSRV_COOKIE_SECURE=true`, monter un volume pour le fichier SQLite. Toute la
config passe par des variables d'environnement `CCSRV_*` (voir
`.env.deploy.example`). Pour servir l'app sous un sous-chemin, builder avec
`VITE_BASE=/<path>/` et `VITE_API_BASE=/<path>`.
