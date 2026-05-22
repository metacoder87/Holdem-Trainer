# PyHoldem Pro Frontend

React frontend for the poker trainer, including gameplay, server-graded quizzes,
guided drills, replay review, bankroll management, and multi-metric analytics.

## Stack
- Vite + React + TypeScript
- DOM/CSS table renderer for gameplay
- ECharts for analytics dashboards

## Run (dev)

```bash
npm install
npm run dev
```

## Checks

```bash
npm run typecheck
npm test
npm run build
```

## Env

Create `.env` from `.env.example` and set `VITE_API_URL` to your FastAPI host.
