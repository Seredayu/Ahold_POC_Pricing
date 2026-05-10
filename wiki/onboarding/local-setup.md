# Local Setup — Phase 1 (Mock Demo)

## Production Deploy

**https://app-blond-ten-78.vercel.app**

Also accessible at: https://app-eo4lso6y4-seredayu-2173s-projects.vercel.app

## Prerequisites

- Node.js 20+
- npm 10+

## Repo Structure

```
src/
  app/        React + Vite + Tailwind (Field App)
  api/        Node/Express mock BFF
wiki/
  architecture/
  onboarding/
docs/
research/
```

## Run Phase 1 Locally

### 1. Start mock BFF

```bash
cd src/api
npm install
npm run dev
# → http://localhost:3001
```

### 2. Start React dev server

```bash
cd src/app
npm install
npm run dev
# → http://localhost:5173
```

Vite proxies `/api/*` → `http://localhost:3001` (configured in `vite.config.js`). Both servers must be running.

### 3. Open in browser

Navigate to `http://localhost:5173`. You should see the Prix Frais / Verse Prijzen field app with markdown recommendations for the 5 synthetic Belgium Delhaize items.

## Environment Variables

`src/api/.env.example` documents all env vars. Copy to `.env` before starting:

```bash
cp src/api/.env.example src/api/.env
```

Phase 1 requires no external credentials — all data is hardcoded.

## What Phase 1 Demonstrates

- AI markdown recommendations sorted by urgency (soonest expiry first)
- XAI reason codes in FR/NL: "17 unités. Vente prévue : 4. Expire dans 6h."
- Confidence score badge (color-coded: green ≥75%, yellow 50–75%, red <50%)
- Low confidence warning (<50%) — associates must review before applying
- Manager required notice (discount >50%)
- One-tap approve → POST /api/approve → mock ZMKD response → "Prix mis à jour. Sync ESL en file."
- Idempotent approve (double-tap shows "Déjà appliqué")
- Reject → dismiss card, show next recommendation
- FR/NL language toggle
- Empty state when all items processed
- Error state with retry when API returns 500
- Offline toast when network drops

## Mock BFF Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/approve | Returns mock ZMKD condition record. Enforces BRE guardrail (discount >50% without manager_override → 403). Idempotent. |
| POST | /api/reject | Records rejection with reason_code. |

## Decision Table Logic (src/app/src/lib/decisionTable.js)

Triggers recommendation when: `hours_to_close < 8 AND stock > 10`

Discount tiers:
- `< 4h` → 40% off
- `< 6h` → 30% off
- `< 8h` → 20% off

Confidence score is **deterministic** (same inputs → same score). Not random.

## Phase 1 Acceptance Criteria

- [ ] Deployed Vercel URL accessible
- [ ] Demo'd to ≥1 Category Manager
- [ ] Manager reaction documented

## Next: Phase 2A Setup

See `wiki/onboarding/phase2a-setup.md` (to be written after Phase 1 ships).
