# Backend — FastAPI + SQLite

Voir le `CLAUDE.md` racine pour l'architecture, les invariants (UPSERT idempotent,
enrichissement, live par snapshots, définition de « tokens ») et les commandes.

## Carte des modules (`app/`)

| Module | Rôle |
|---|---|
| `main.py` | `create_app()`, `lifespan` (init DB, load CSV, boucle snapshots), montage du SPA |
| `config.py` | `Settings` Pydantic (`CCSRV_*`), `get_settings()` mémoïsé (`@lru_cache`) |
| `db.py` | Connexion SQLite unique, `SCHEMA`, migrations, `now_utc()`, `write_lock()` |
| `models.py` | Modèles Pydantic — contrat d'ingest (miroir du client) + DTO de réponse |
| `auth.py` | Auth ingest (Bearer) + auth dashboard (cookie signé `itsdangerous`) |
| `ingest.py` | Routeur `/ingest` + `/api/eval` — l'UPSERT des sessions |
| `enrichment.py` | Chargement/jointure du CSV participants ; bucket `UNKNOWN` |
| `metrics.py` | Toutes les requêtes d'agrégation (SQL) pour le dashboard |
| `live.py` | `/api/live/snapshot` + `/api/live/stream` (SSE) |
| `snapshots.py` | `snapshot_loop()` — tâche de fond qui écrit `agg_snapshot` |
| `routes_dashboard.py` | login/logout/me/config + leaderboards + admin participants |

## Conventions

- **Une seule connexion SQLite** (`db.get_conn()`), partagée processus-wide, en mode
  **WAL**. Sérialiser **toutes les écritures** sous `db.write_lock()` ; les lectures
  sont concurrentes. Ne pas ouvrir d'autres connexions.
- **Migrations** : `CREATE TABLE IF NOT EXISTS` n'altère jamais une table existante.
  Toute colonne ajoutée doit être backfillée via `_ensure_column()` dans `init_db()`.
- **Horloge serveur uniquement** (`now_utc()`) pour l'ordonnancement et la liveness —
  ne jamais se fier aux timestamps du client.
- **Modèles d'ingest en `extra="ignore"`** : un nouveau champ côté client ne doit
  jamais provoquer un 422 (sinon tempête de retries at-least-once).
- **Colonnes JSON** (`models`, `*_counts`…) stockées en TEXT, sérialisées/parsées
  explicitement. `metrics.py` centralise les expressions SQL réutilisées
  (`TOKENS_SQL`, `TEAM_EXPR`, `_live_cutoff`) — réutiliser ces constantes.
- Dépendances FastAPI pour l'auth : `Depends(require_ingest_token)` /
  `Depends(require_dashboard)`.

## Tests (`tests/`)

`pytest` (`asyncio_mode=auto`). Les fixtures de `conftest.py` pointent l'app vers
une DB + un CSV temporaires via `monkeypatch.setenv("CCSRV_*")` et appellent
`get_settings.cache_clear()` (sinon le `@lru_cache` garde l'ancienne config).
Utiliser les fixtures `client`, `logged_in`, `auth_headers`, `payload`.
