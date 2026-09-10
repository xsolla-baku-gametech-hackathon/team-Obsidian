# Launchpad frontend

A simple React + TypeScript landing page: enter a Steam store game link and confirm
it to open a large report dialog with blurred placeholders behind a paywall card.

```bash
cd apps/web
npm install
npm run dev
```

`npm run build` checks TypeScript and creates the production build. `npm run preview`
serves the build locally.

The form validates HTTPS Steam store app URLs and normalizes the app ID link. This
confirms URL format only; game existence is not checked. Invalid links show inline
errors. The native dialog supports keyboard focus containment, Escape, and closing
back to the form. Layout adapts to mobile screens.

This is a frontend preview: results are decorative placeholders and checkout is not
connected. The unlock button explains that paid reports are coming soon. No price is
invented and no payment is taken. A production integration must verify games, generate
reports, authorize paid access on the server, and connect checkout before serving real
results. Google Fonts are optional; system sans-serif works offline.

Earlier dashboard feature components and synthetic fixtures remain available in
`src/features` and `src/lib/api` for later integration, but are not rendered by this flow.
