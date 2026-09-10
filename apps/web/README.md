# Launchpad frontend

A React + TypeScript launch workspace. Anonymous visitors see a welcome page, signed-in
users choose a premium plan and account type, and active premium users can enter a
Steam store game link from the dashboard workspace to generate a report with real
catalog matches and live Steam price comparisons. Logged-in navigation includes
Dashboard, My Reports, Steam analysis, and Account pages.

```bash
# Starts the FastAPI backend and Vite frontend together.
./scripts/dev.sh
```

For frontend-only work:

```bash
cd apps/web
npm install
npm run dev
```

`npm run build` checks TypeScript and creates the production build. `npm run preview`
serves the build locally.

The report form is only shown for active premium accounts. It validates HTTPS Steam
app URLs, then calls `POST /api/v1/steam/games/analyze` with the user's bearer token.
The API looks up the target, finds catalog neighbors, refreshes prices, and runs the
shared recommendation model. Successful reports are saved automatically and can be
reopened from My Reports without calling Steam again. The analysis page shows
loading, error/retry, and real-result states. If Steam is unavailable, catalog matches
can still appear with an explicit source warning and no invented prices.

Vite development and preview servers proxy `/api` to `http://127.0.0.1:8000`. Restart
Vite if it was started before this proxy configuration existed. For a separately
hosted API, set `VITE_API_BASE_URL` at build time and configure API CORS accordingly.
The current form uses the US market and the next 90 days. The API also supports an
explicit date range and country code. The supplied CSV has no future releases, so
release advice explicitly explains that upcoming data is needed. No mock results
are shown. Checkout remains disconnected; selecting a plan updates local account
state but does not take payment.

Earlier dashboard feature components and synthetic fixtures remain available in
`src/features` and `src/lib/api` for later integration, but are not rendered by this flow.
