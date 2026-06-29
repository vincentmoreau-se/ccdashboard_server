# Frontend — React + Vite + Tailwind

Voir le `CLAUDE.md` racine pour l'architecture, les ports et les commandes.
SPA esthétique « flight-deck / mission-control », intégralement en français côté UI.

## Structure (`src/`)

- `main.tsx` — bootstrap (QueryClient, `BrowserRouter basename={import.meta.env.BASE_URL}`)
- `App.tsx` — routes, garde `RequireAuth`, `Shell` (header/nav/footer)
- `api/client.ts` — client REST typé (`api.*`) + interfaces partagées des réponses
- `api/sse.ts` — abonnement au flux live SSE
- `pages/` — une page par route (`WarRoom`, `Leaderboard`, `History`, `TeamDetail`, `TechTooling`, `Login`)
- `components/hud.tsx` — primitives visuelles (panneaux, fonds, overlay de boot)
- `lib/format.ts` — formatage tokens / coût / nombres (locale `fr-FR`)

## Conventions

- **Données via TanStack Query** uniquement, en passant par `api.*` de
  `api/client.ts`. Ne pas appeler `fetch` ailleurs ; ajouter une nouvelle route =
  une méthode `api.*` + son interface de réponse au même endroit (source de vérité
  des types, alignée sur les DTO Pydantic backend).
- **Cookie de session** : `fetch` utilise `credentials: "include"`. En dev tout est
  same-origin grâce au proxy Vite ; pour un déploiement scindé, surcharger
  `VITE_API_BASE`. Un `401` lève `ApiError(401)` → redirection vers `/login`.
- **Auth** : route protégée = enfant de `RequireAuth` (interroge `api.me`).
- **Style = Tailwind + tokens** définis dans `tailwind.config.js`. Réutiliser les
  couleurs nommées (`brand`/`deep` = bleus Capgemini, `live`, `alert`, `void`,
  `panel`, `ash`, `haze`, `bone`…), polices `font-display` / `font-mono`, et les
  animations HUD (`flicker`, `sweep`, `glow-pulse`, `boot-bar`). Pas de couleurs
  ni de hex en dur — étendre le thème plutôt.

## Tests E2E (`tests/`)

Playwright (chromium). Supposent backend (8090, seedé) + Vite (5180) déjà lancés.
Helpers de login partagés dans `tests/helpers.ts`.

## Piège build sous-chemin

`tsc -b` a déjà émis un `vite.config.js`/`.d.ts` à côté du `.ts` (Vite charge le
`.js` en premier → proxy périmé). Le `outDir` de `tsconfig.node.json` + le
`.gitignore` corrigent ça — ne pas laisser ces fichiers réapparaître.
