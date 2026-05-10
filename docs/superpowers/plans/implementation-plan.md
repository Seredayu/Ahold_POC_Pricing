# Implementation Plan: Ahold Delhaize Dynamic Freshness Pricing POC

**Generated:** 2026-05-10  
**Branch:** master  
**Status:** APPROVED WITH CONDITIONS (CEO + Design + Eng reviews complete)

---

## Problem

Store managers manually review up to 1,000 order lines daily (06:00–08:00). Fresh produce pricing is driven by static min/max rules — no shelf-life decay, no real-time demand signals. Result: €200M+ annual perishable waste, €350M+ EBITDA left unrealised.

## POC Wedge

One full-loop trigger: AI recommends markdown → store associate approves → ZMKD condition record created in SAP ECC 6.0 → ESL updates automatically.

---

## Architecture (Production Target)

```
SAP ECC 6.0 (MM-IM / KONV)
    │ BODS RFC/ODP — KONV is a cluster table, no CDC
    │ Lakeflow Connect CDC — MM-IM stock + EWM SLED (sub-minute)
    ▼
Databricks Bronze → Silver (Freshness Ledger) → Gold (Recommended Price Table)
    ▼
M2 XGBoost (expiry risk 72h) → M3 RL/XGBoost (exact markdown %, e.g. 18%)
    ▼
BRE: margin floor check + >50% discount → manager dashboard
    ▼
React Field App (associate scans barcode → one-tap "Execute Markdown")
    ▼
Node.js BFF (Azure) → SAP BTP Cloud Connector → BAPI_PRICES_CONDITIONS
                                                          ↓
                                             ZMKD in SAP A004
                                             POS + ESL + Hybris sync instantly
                                                          ↓
                                   async → S/4HANA P&L (price variance)
                                   async → Delta Lake (manager decision → retrain)
```

---

## Phase 1 — Mock Demo (Weeks 1–2)

**Goal:** Deployable demo artifact to create stakeholder pull. Zero blocked dependencies.

### What to Build

**React Field App (`src/app/`)**
- React + Vite + Tailwind CSS — mobile-first
- Hardcoded decision table: `if hours_to_close < 8 AND stock > 10 → recommend markdown`
- `recommended_price = current_price * (1 - 0.40)` — hardcoded 40% for Phase 1

**Each recommendation card shows:**
- Item name (truncated to 40 chars, full name on detail tap)
- Current price → recommended price (e.g. €1.49 → €0.89 −40%)
- Stock level + expiry countdown (hours)
- Confidence score badge (deterministic from decision table, e.g. 0.82)
- XAI reason in FR/NL: `"17 unités. Vente prévue: 4. Expire dans 6h."` / `"17 stuks. Verwachte verkoop: 4. Vervalt in 6u."`
- Approve / Reject CTAs

**Screens:**
1. Recommendation List — sorted by urgency (hours_to_close ascending)
2. Detail View — expanded reason, approve/reject/alternatives
3. Confirmation — `"Prix mis à jour. Sync ESL en file."` / `"Prijs bijgewerkt. ESL sync in wachtrij."` — green banner
4. Empty State — `"Pas de recommandations pour l'instant. Revérifiez après 14:00."` (not a spinner)

**UX requirements (non-negotiable in Phase 1):**
- Empty state: explain why + when to check back
- Error state: "Impossible de synchroniser. Réessayer." + retry CTA (not white screen)
- Double-tap idempotent: second POST /approve same item → return "Already applied", no duplicate
- Confidence score < 0.5 → show "Faible confiance — vérifier avant d'appliquer"
- Offline: toast "Hors ligne — synchronisation à la reconnexion" (no actual queue in Phase 1)
- >50% discount → route to manager dashboard (not direct approve)

**Mock BFF (`src/api/`)**
- Node.js + Express
- `POST /api/approve` → returns mock BAPI_PRICES_CONDITIONS response:
  ```json
  {
    "status": "zmkd_queued",
    "condition_record": "0000012345",
    "condition_type": "ZMKD",
    "table": "A004",
    "discount_pct": 0.18,
    "valid_from": "2026-05-10T00:00:00Z",
    "valid_to": "2026-05-10T23:59:59Z"
  }
  ```
- `POST /api/reject` → logs action, returns next recommendation
- Schema is frozen — Phase 2 swap = URL change only

### Deliverable
- Deployed Vercel URL (public)
- Demo'd to one Category Manager
- Their reaction documented (photo/notes)

### Parallel Track (non-blocking for Phase 1)
Find Belgium Delhaize IT owner of SAP BTP subaccount. Send email week 1. Goal: confirm ZMKD condition type in A004 + get staging BTP credentials.

---

## Phase 2A — Real ML, Supabase Proxy (Weeks 3–6)

**Prerequisites:** Named sponsor secured via Phase 1 demo.

### Data

**Dataset:** Rossmann Store Sales (Kaggle)
- 1,115 stores, 2.5 years daily sales, ~38MB CSV
- Filter to single store → ~12MB (fits Supabase free 500MB)
- Add synthetic column: `shelf_life_hours` (EWM SLED equivalent)

**Supabase schema:**
```sql
CREATE TABLE inventory_features (
  item_id        TEXT PRIMARY KEY,
  name_fr        TEXT,
  name_nl        TEXT,
  current_price  NUMERIC(10,2),
  stock          INTEGER,
  shelf_life_hours INTEGER,          -- synthetic SLED proxy
  sales_velocity_7d NUMERIC(10,4),  -- units/day rolling 7d
  inventory_age_days INTEGER,
  hour_of_day    INTEGER,
  weather_signal NUMERIC(5,2),       -- synthetic
  price_history_7d JSONB
);
```

**Feature vector (FROZEN — must match Phase 2B Feature Store exactly):**
```
inventory_age_days, stock_pressure, hour_of_day,
sales_velocity_7d, weather_signal, price_history_7d
```

### ML Pipeline (`src/ml/`)

```
seed_data.py          ← Rossmann CSV → Supabase + synthetic SLED column
feature_pipeline.py   ← query Supabase → flat feature vector
train_m2.py           ← XGBoost classifier, expiry_risk_score (72h horizon)
train_m3.py           ← XGBoost regressor, discount_pct output
evaluate.py           ← precision/recall M2, margin recovery M3
export_model.py       ← pickle to models/m2.pkl + models/m3.pkl
```

### Inference API (`src/api/`)

FastAPI on Railway/Render:
```
POST /infer
  body: {item_id, ...feature_vector}
  returns: {expiry_risk: 0.87, discount_pct: 0.18, confidence: 0.82,
            reason_fr: "...", reason_nl: "..."}

POST /approve
  body: {item_id, applied_discount_pct, manager_override: bool}
  returns: {status: "zmkd_queued", condition_record, ...}
  validates: item_id exists in active recommendation set
  requires: API key header X-API-Key

POST /reject
  body: {item_id, reason_code}
  returns: {status: "logged"}
```

**Security:**
- `X-API-Key` header required on all endpoints — reject 401 if missing
- Validate `item_id` on `/approve` — reject 422 if not in active recommendation set
- All credentials in `.env`, never hardcoded

### Infrastructure (Phase 2A)

| Component | Service |
|-----------|---------|
| Data / DB | Supabase Postgres (free tier) |
| ML training | Local + GitHub Actions |
| Model serving | FastAPI on Railway/Render |
| Frontend | Vercel |
| CI/CD | GitHub Actions |

---

## Phase 2B — Databricks Medallion (Weeks 7–12)

**Prerequisites:** SAP RFC access live (2026-05-29) + SAP BTP Cloud Connector configured.

### Databricks Solution Accelerator

Start from: `databricks-industry-solutions/price-optimization`

**Accelerator provides:** DLT pipeline skeleton, MLflow experiment + registry pattern, Feature Store definitions, sample data generator.

**Required customisations:**
1. Add `shelf_life_hours` / SLED dimension — freshness-aware pricing, not just demand elasticity
2. Replace synthetic data with KONV/SLED feed from SAP ECC
3. Add `BAPI_PRICES_CONDITIONS` write-back layer (accelerator stops at "recommended price")
4. Add BRE margin floor guardrail (not in standard accelerator)

### Medallion Pipeline (`src/pipeline/`)

```
Bronze:
  bods_konv_ingest.py      ← BODS RFC/ODP delta → Bronze KONV pricing table
  lakeflow_stock_ingest.py ← Lakeflow CDC → Bronze MM-IM stock + EWM SLED

Silver:
  freshness_ledger.sql     ← DLT: join(SLED, stock, POS_velocity, weather)

Gold:
  recommended_price.sql    ← DLT: M2 expiry_risk_score + M3 discount_pct output
```

**Important:** KONV is a cluster table — use BODS RFC/ODP with delta pointers (nightly batch). Do NOT use Lakeflow CDC for pricing tables — CDC only works on transparent tables.

### Feature Store

```
Features (identical to Phase 2A schema — frozen):
  inventory_age_days, stock_pressure, hour_of_day,
  sales_velocity_7d, weather_signal, price_history_7d

Feature table: freshness_features (keyed on item_id + store_id + date)
Served to: M2 XGBoost, M3 XGBoost/RL at inference time
```

### Models

| Model | Type | Input | Output |
|-------|------|-------|--------|
| M2 — Predictive Expiry | XGBoost classifier | Freshness features | `expiry_risk_score` (0–1) |
| M3 — Dynamic Pricing | XGBoost regressor (POC) / PPO RL (production) | Freshness features + M2 output | `discount_pct` (e.g. 0.18) |

MLflow: experiment tracking + Model Registry (staging → production promotion).

Model Serving endpoint:
```
POST /serving-endpoints/m3-freshness/invocations
  body: {dataframe_records: [{item_id, ...features}]}
  returns: {predictions: [{discount_pct, expiry_risk, confidence, reason_fr, reason_nl}]}
```

### Retraining Loop

Manager decision logged on every approve/reject:
```json
{"item_id": "...", "manager_override": false, "actual_discount_pct": 0.18,
 "units_sold_post_markdown": 14, "timestamp": "..."}
```
Delta Lake event → MLflow incremental retrain job → promotes new model version if metric improves.

### Write-back (SAP BTP Cloud Connector)

```
Node.js BFF (Azure Container Apps)
    └── SAP BTP Cloud Connector (RFC tunnel)
            └── BAPI_PRICES_CONDITIONS (RFC call)
                    └── ZMKD record in SAP table A004
                            ├── ValidFrom / ValidTo timestamps
                            ├── ESL auto-flicker (vendor-agnostic)
                            ├── POS register updated instantly
                            └── async → SAP Event Mesh → Hybris Flash Sale
```

Error handling:
- BAPI return code non-zero → display `"Mise à jour en attente. Réf: [condition_record]"` — never silent success
- A004 lock → retry once after 500ms, then surface to manager

### Infrastructure (Phase 2B)

| Component | Service |
|-----------|---------|
| Data / DB | Databricks Lakehouse (Delta, Unity Catalog) |
| Feature store | Databricks Feature Store |
| Model training | Databricks ML + MLflow |
| Model serving | Databricks Model Serving |
| API / BFF | Node.js on Azure Container Apps |
| Frontend | Azure Static Web Apps (or Vercel) |
| Storage | Azure Blob Storage (ADLS Gen2) |
| IaC | Terraform (Databricks workspace + Azure) |
| Ingestion | BODS RFC/ODP (KONV) + Lakeflow Connect (stock + SLED) |

---

## Repo Structure

```
src/
  app/          # React + Vite + Tailwind (Phase 1+)
  api/          # Node.js BFF + FastAPI inference (Phase 1+)
  ml/           # Python: seed, feature pipeline, train, evaluate (Phase 2A+)
  pipeline/     # Databricks notebooks: Bronze/Silver/Gold DLT (Phase 2B)
infra/
  terraform/    # Azure Databricks workspace + ACA (Phase 2B)
  btp/          # SAP BTP Cloud Connector config (Phase 2B)
tests/
  unit/         # Decision table, markdown calc, confidence score
  integration/  # FastAPI /infer latency, Supabase read
  e2e/          # Approve flow, reject flow, idempotent approve
docs/
  superpowers/
    plans/
      implementation-plan.md   ← this file
```

---

## Markdown / Liftup Cases

**POC scope: Dynamic Freshness (M3) only.** All other cases Phase 3+.

| Case | ZMKD Pattern | BAPI |
|------|-------------|------|
| Dynamic Freshness (M3) — **POC** | Single ZMKD | `BAPI_PRICES_CONDITIONS` |
| Golden Hour | Timed ZMKD ValidFrom 16:00 ValidTo 19:00 | `BAPI_PRICES_CONDITIONS` |
| Markdown Ladder | 5× sequential ZMKD pre-staged at 06:00 AM | `BAPI_PRICES_CONDITIONS` |
| Weather Liftup (price UP) | Dual ZMKD: positive + markdown | `BAPI_PRICES_CONDITIONS` |
| Green Leaf Premium | ZMKD + ESG metadata → Unity Catalog | `BAPI_PRICES_CONDITIONS` |
| Bundle Intelligence | SD Bundle Condition (no ZMKD) | `BAPI_SALESORDER_CREATEFROMDAT2` |
| B2B Rescue | No ZMKD (B2B revenue line) | `BAPI_SALESORDER_CREATEFROMDAT2` |
| Cross-Store Transfer | No ZMKD (inter-store stock movement) | `BAPI_GOODSMVT_CREATE` |
| Loyalty Personalisation | Member-specific condition | SAP Loyalty Engine |

---

## Pre-Build Checklist

- [ ] **ZMKD mock schema frozen** — `{status, condition_record, condition_type:"ZMKD", table:"A004", discount_pct, valid_from, valid_to}`. Phase 2 = URL swap only.
- [ ] **Feature schema frozen** — `inventory_age_days, stock_pressure, hour_of_day, sales_velocity_7d, weather_signal, price_history_7d` — identical in 2A (Python dict) and 2B (Feature Store). Never diverge.
- [ ] **Rossmann dataset downloaded** — kaggle.com/c/rossmann-store-sales. Filter to Store=1. Add synthetic `shelf_life_hours`.
- [ ] **Supabase project created** — free tier. Run `seed_data.py`.
- [ ] **Databricks accelerator cloned** — `databricks-industry-solutions/price-optimization`. Evaluate before building 2B from scratch.
- [ ] **SAP BTP Cloud Connector contact named** — Belgium IT owner of BTP subaccount. RFC access 2026-05-29 is useless without BTP tunnel. Email by end of week 1.
- [ ] **FastAPI API key generated** — in `.env`. Add to Vercel/Railway env vars. Never commit.
- [ ] **Phase 1 acceptance criteria met** — Vercel URL live + demo to one Category Manager + reaction documented.
- [ ] **Works Council flag set** — Belgian CAO/CCT: each new approve-markdown task must offset a legacy ECC manual task. Validate before Phase 2 go-live.

---

## Key Decisions Made

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Phase 1 mock → Phase 2A Supabase → Phase 2B Databricks | Sponsor needed before ML investment; Supabase proves logic fast |
| 2 | Write-back: BAPI_PRICES_CONDITIONS / ZMKD (not Symphony Gold) | Belgium Delhaize uses SAP ECC 6.0; Symphony Gold = training data only |
| 3 | BODS for KONV ingestion (not Lakeflow CDC) | KONV is cluster table; CDC only reads transparent tables |
| 4 | Feature schema frozen before Phase 2A build | 2A→2B migration must be infrastructure swap, not feature engineering rewrite |
| 5 | Databricks price-optimization accelerator as 2B baseline | Cuts 6 weeks → 3 weeks; needs SLED dimension + ERP write-back added |
| 6 | XAI reason codes in FR/NL mandatory in Phase 1 | Belgium bilingual; required for Works Council trust + CAO/CCT compliance |
| 7 | >50% discount routes to manager dashboard | BRE guardrail from Architecture.md — do not remove |

---

## Not In Scope (This POC)

- M4 Freshness-Aware Replenishment
- M5 Supplier Freshness Scoring
- Phantom Stock Engine
- Logistics Constraint Solver
- Omni-channel Flash Sales (SAP Event Mesh → Hybris)
- S/4HANA financial write-back
- Demand Forecasting engine
- Power BI / SAP Analytics Cloud dashboards
- Multi-store deployment
- Golden Hour, Markdown Ladder, Weather Liftup, Green Leaf, Bundle, B2B Rescue, Cross-Store Transfer
