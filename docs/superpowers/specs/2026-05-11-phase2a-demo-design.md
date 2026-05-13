# Phase 2A Demo Design

**Date:** 2026-05-11
**Status:** Approved
**Audience:** Category Manager (same as Phase 1)
**Goal:** Real XGBoost M2+M3 replacing mock decision table — visible upgrade on the existing card

---

## Context

Phase 1 ships a hardcoded decision table with 3 fixed discount tiers (20/30/40%). Phase 2A replaces the backend with real ML while keeping the same React app shell. The Category Manager sees two new signals: a precise ML discount (e.g. 38.4% not 40%) and an expiry risk bar. The demo expands from 5 to 12 Belgium Bakery & Deli items.

---

## Architecture

```
Supabase Postgres (inventory_features, 12 items)
    ↓ feature vector (6 fields, frozen schema)
FastAPI on Railway  ←  POST /infer  ←  Node BFF (Vercel, unchanged)
    XGBoost M2 (expiry_risk)                      ↓
    XGBoost M3 (discount_pct)          React App (Vercel)
    SHAP top-3 → reason_fr/nl          Enhanced card
```

**What stays identical:** ZMKD mock response shape, `/api/approve` + `/api/reject` endpoints, feature schema 6 fields, bilingual FR/NL, >50% manager gate.

**What changes:** discount_pct from M3 (not fixed tier), expiry_risk from M2 (new bar on card), richer XAI reason (SHAP top-3), 12 items (not 5), real ML confidence.

---

## Data Layer

### Supabase table: `inventory_features`

```sql
CREATE TABLE inventory_features (
  item_id            TEXT PRIMARY KEY,
  name_fr            TEXT,
  name_nl            TEXT,
  current_price      NUMERIC(10,2),
  stock              INTEGER,
  shelf_life_hours   INTEGER,          -- synthetic SLED proxy
  sales_velocity_7d  NUMERIC(10,4),
  inventory_age_days INTEGER,
  stock_pressure     NUMERIC(5,4),     -- stock / max_stock
  hour_of_day        INTEGER,
  weather_signal     NUMERIC(5,2),     -- 0–1 synthetic
  price_history_7d   JSONB,            -- [p1..p7]
  expiry_risk        NUMERIC(5,4),     -- M2 output, cached
  discount_pct       NUMERIC(5,4)      -- M3 output, cached
);
```

### 12 Demo items (sorted by urgency)

| item_id | name_fr | price | stock | shelf_life_h | velocity_7d |
|---------|---------|-------|-------|-------------|-------------|
| SKU-002 | Poulet rôti Label Rouge 1.2kg | 9.99 | 8 | 3h | 2.8 |
| SKU-008 | Baguette tradition x2 | 1.79 | 28 | 3h | 9.4 |
| SKU-005 | Pain de campagne 400g | 2.49 | 31 | 4h | 11.6 |
| SKU-006 | Quiche Lorraine 4 personnes | 5.49 | 11 | 4h | 3.1 |
| SKU-003 | Croissants beurre x6 | 2.89 | 24 | 5h | 9.1 |
| SKU-010 | Fromage frais aux herbes 200g | 2.29 | 16 | 5h | 5.2 |
| SKU-001 | Fraises biologiques 500g | 3.49 | 17 | 6h | 4.2 |
| SKU-007 | Tarte aux pommes 6 parts | 3.99 | 14 | 6h | 4.8 |
| SKU-011 | Wrap poulet César 220g | 3.19 | 19 | 6h | 6.7 |
| SKU-004 | Saumon fumé 200g | 5.99 | 12 | 7h | 3.4 |
| SKU-009 | Jambon cuit tranché 150g | 2.99 | 22 | 7h | 7.1 |
| SKU-012 | Soupe de légumes 600ml | 2.79 | 18 | 7h | 5.9 |

Each item has a Dutch name equivalent in `name_nl`. `mockData.js` is retired — items come from Supabase via FastAPI at request time.

---

## ML Pipeline (`src/ml/`)

### Files

| File | Purpose |
|------|---------|
| `seed_data.py` | Rossmann Store 1 CSV → Supabase. Adds synthetic `shelf_life_hours`, `weather_signal`, `price_history_7d`. Maps sales → `sales_velocity_7d`. |
| `feature_pipeline.py` | Queries Supabase → flat 6-field feature vector per item. |
| `train_m2.py` | XGBoost classifier. Label: `shelf_life_hours < 6`. Output: `expiry_risk` 0–1. |
| `train_m3.py` | XGBoost regressor. Target: synthetic discount label. Output: `discount_pct` 0–0.5. |
| `export_model.py` | joblib → `models/m2.pkl` + `models/m3.pkl` + `models/shap_m3.pkl` (top-3 SHAP for XAI). |

### XAI reason generation

Top-3 SHAP feature names from M3 are mapped to bilingual templates:

| Feature | reason_fr token | reason_nl token |
|---------|----------------|----------------|
| stock_pressure | "stock élevé" | "hoge voorraad" |
| hour_of_day | "fin de journée" | "einde dag" |
| sales_velocity_7d | "ventes en baisse" | "dalende verkoop" |
| weather_signal | "météo défavorable" | "slecht weer" |
| inventory_age_days | "stock ancien" | "oud voorraad" |
| price_history_7d | "historique prix stable" | "stabiele prijshistorie" |

Reason is 3 tokens joined with " · ". Deterministic — no LLM.

---

## FastAPI Inference API (`src/api/infer.py`)

Deployed to Railway. Loads pickles at startup.

### `POST /infer`

**Request:**
```json
{
  "item_id": "SKU-002",
  "inventory_age_days": 2,
  "stock_pressure": 0.72,
  "hour_of_day": 17,
  "sales_velocity_7d": 2.8,
  "weather_signal": 0.3,
  "price_history_7d": [9.99, 9.99, 9.99, 9.99, 9.99, 9.99, 9.99]
}
```

**Response:**
```json
{
  "expiry_risk": 0.87,
  "discount_pct": 0.384,
  "confidence": 0.91,
  "reason_fr": "stock élevé · fin de journée · ventes en baisse",
  "reason_nl": "hoge voorraad · einde dag · dalende verkoop"
}
```

**Auth:** `X-API-Key` header required. 401 if missing/invalid.

**`GET /health`** — returns `{"status":"ok"}` for Railway health check.

### `POST /approve` and `POST /reject`

Kept on Node BFF (`src/api/server.js`) — unchanged. BFF calls `/infer` internally when serving the item queue, caches result per item_id for the session.

---

## BFF Changes (`src/api/server.js`)

1. Add `GET /api/items` — queries Supabase, calls `/infer` for each item, returns enriched list with `expiry_risk`, `discount_pct`, `confidence`, `reason_fr`, `reason_nl`.
2. Existing `/api/approve` and `/api/reject` unchanged.
3. New env vars: `RAILWAY_URL`, `INFER_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`.

---

## Frontend Changes (`src/app/`)

### Card additions (bilingual)

New i18n keys:
- `expiryRiskLabel` — "Risque expiration" / "Vervalrisico"
- `reason` — now uses `reason_fr`/`reason_nl` from API instead of local template

### `RecommendationCard.jsx` additions

1. Expiry risk bar (gradient yellow→red, value from `rec.expiry_risk`)
2. Summary line gains weather + sales trend from API `reason_fr`/`reason_nl`
3. Precise discount display: `38.4 %` not `40 %` (already handled by `discountLabel` formatter)

### `App.jsx` changes

- Replace `buildQueue(MOCK_ITEMS)` with `GET /api/items` fetch on mount
- `mockData.js` no longer imported (file kept but unused until deleted in cleanup)

---

## Deployment

| Component | Service | New env vars |
|-----------|---------|-------------|
| FastAPI | Railway (free) | `INFER_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` |
| Node BFF | Vercel (existing) | `RAILWAY_URL`, `INFER_API_KEY` |
| React App | Vercel (existing) | none |
| Supabase | Supabase free tier | — |

---

## Security

- `X-API-Key` on all `/infer` calls — BFF holds the key, never exposed to frontend
- Supabase anon key used read-only from FastAPI — no write access from inference path
- All credentials in `.env`, added to `.gitignore`, set as Vercel/Railway env vars

---

## Out of Scope

- MLflow experiment tracking (Phase 2B)
- Retraining loop (Phase 2B)
- Real Rossmann → Belgium item name mapping (synthetic names sufficient for demo)
- GitHub Actions CI for model training (manual local training for Phase 2A demo)
- Unit tests for ML pipeline (Phase 2A acceptance = demo reaction, not test suite)
