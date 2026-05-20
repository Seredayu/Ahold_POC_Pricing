# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Local development (run both terminals simultaneously)

**Phase 2A (FastAPI + real ML):**

```bash
# Terminal 1 — FastAPI inference server (http://localhost:8000)
# Auto-trains M2+M3 on first start if models/ is empty
cd src/ml && uvicorn inference:app --port 8000 --reload

# Terminal 2 — React Field App (http://localhost:5173)
cd src/app && npm install && npm run dev
```

Vite proxies `/api/*` → `http://localhost:8000`.

**Phase 1 (mock BFF, for reference):**

```bash
# Terminal 1 — Mock BFF (http://localhost:3001)
cd src/api && npm install && npm run dev
# Also revert vite.config.js proxy to port 3001
```

**ML pipeline (run once before starting inference server):**

```bash
cd src/ml
pip install -r requirements.txt
python seed_data.py        # seed 12 demo items to Supabase (if not done)
python export_model.py     # train M2+M3, save models/m2.pkl + m3.pkl
python evaluate.py         # LOO-CV metrics report
```

```bash
# Lint
cd src/app && npm run lint

# Production build
cd src/app && npm run build

# Preview production bundle locally
cd src/app && npm run preview
```

No test suite exists yet (Phase 1 acceptance criterion is demo feedback, not automated tests).

## Architecture

**3-phase AI pricing POC for Belgium Delhaize stores.** Store associates scan near-expiry items; the system recommends markdowns and write the approved price back to SAP ECC 6.0.

### Phase 1 (live, deployed to Vercel)

```
React Field App (src/app)
  ↓ POST /api/approve | /api/reject
Node.js Mock BFF (src/api)
  ↓ returns mock ZMKD response (condition_record in SAP A004)
```

Data: 5 hardcoded Belgium Delhaize items in `src/app/src/lib/mockData.js`.  
ML: Deterministic decision table in `src/app/src/lib/decisionTable.js` — **schema frozen**.  
Discount tiers: `< 4h` to close → 40%, `< 6h` → 30%, `< 8h` → 20%.

### Phase 2A (planned — real ML, Supabase)

Replaces mock BFF with FastAPI. Replaces decision table with XGBoost (M2 expiry risk + M3 discount %). Feature schema must stay identical to Phase 2B.

### Phase 2B (planned — real SAP integration)

```
Databricks Lakehouse (Bronze→Silver→Gold via DLT)
  ↑ BODS RFC/ODP (KONV cluster table, nightly batch)
  ↑ Lakeflow Connect CDC (MM-IM stock + EWM SLED)
  ↓
Node.js BFF → SAP BTP Cloud Connector → BAPI_PRICES_CONDITIONS → ZMKD in A004
```

SAP RFC access available 2026-05-29. Target: 5 pilot stores, Brooks region, Bakery & Deli.

## Key files

| File | Purpose |
|------|---------|
| `src/app/src/App.jsx` | Main React component — state, queue, approve/reject/undo flow |
| `src/app/src/lib/decisionTable.js` | **Frozen** decision logic + feature schema; must match Phase 2B Feature Store |
| `src/app/src/lib/mockData.js` | 5 hardcoded Belgium Delhaize items (Phase 1 only) |
| `src/app/src/lib/api.js` | `postApprove()` / `postReject()` fetch wrappers |
| `src/app/src/lib/i18n.js` | FR/NL translations (FR default; bilingual mandatory) |
| `src/api/server.js` | Mock BFF: validates discount >50% requires `manager_override`, idempotent via Set |
| `wiki/architecture/integration-flow.md` | Full SAP→Databricks→App→BAPI data flow diagram |
| `wiki/architecture/data-models.md` | Item/Recommendation interfaces, feature schema |
| `docs/superpowers/plans/implementation-plan.md` | 3-phase roadmap + pre-build checklist |

## Documentation

When making significant architecture, technology, or integration decisions:

1. Add an ADR entry to `docs/decisions.md` (format: ADR-NNN, date, status, decision, rationale).
2. Update `wiki/architecture/` if the data flow, data model, or phase comparison table changes.
3. Update the Key files table in this file if a new file becomes load-bearing.

Do not commit phase transitions, integration changes, or frozen-schema modifications without updating docs.

## Constraints

- **Feature schema frozen** — `decisionTable.js` feature fields must stay identical across Phase 1 (Python dict), 2A (FastAPI), 2B (Databricks Feature Store). Do not add/rename fields without updating all three.
- **Bilingual mandatory** — All UI strings go through `i18n.js` (FR + NL). No hardcoded display text.
- **>50% discount** requires `manager_override: true` from the frontend; the BFF enforces this.
- **ZMKD condition type / A004 table** — write-back schema is defined; do not alter the mock response shape (`status`, `condition_record`, `condition_type`) as Phase 2B depends on it.
- **KONV is a cluster table** — no CDC; ingestion must use BODS RFC/ODP (nightly batch), not Lakeflow.
- Belgian CAO/CCT Works Council approval required before Phase 2 go-live.
