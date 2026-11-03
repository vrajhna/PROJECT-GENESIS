# Genesis frontend — command center

Dark precision console for the Phase 1–2 vertical slice. Shows recorded
verification data only — no invented statistics.

## Start (not currently running — not verified here)

```sh
cd genesis/frontend
npm install
npm run dev
```

Then open http://localhost:3000 in a browser.

## What works without the backend

- Spec textarea → deterministic requirement preview (mirrors
  `backend/app/spec/engine.py`).
- Model routing label (Spark routine / Wonder complex).
- Recorded ledger: backend suite `11 passed / 1 skipped`, live `/models`
  `1169 ms`, both model IDs confirmed on API 2026-11-02.

## Pending

Backend wiring (`POST /api/projects/:id/specification`), live event
stream, `npm run build` green on this machine.
