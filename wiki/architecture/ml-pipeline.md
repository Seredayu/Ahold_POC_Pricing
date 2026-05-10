# ML Pipeline

## Model Map

| Model | Role | Phase | Source Tables |
|-------|------|-------|---------------|
| M2 | Predictive Expiry (XGBoost classifier) | Phase 2A+ | EWM SLED + POS velocity |
| M3 | Dynamic Pricing (XGBoost regressor → RL agent) | Phase 2A+ | Freshness Ledger Gold |
| M4 | Freshness-Aware Replenishment | Phase 3 | EWM SLED + MM lead times |
| M5 | Supplier Freshness Scoring | Phase 3 | GR SLED + quality rejection |

**POC scope: M2 + M3 only.**

## Phase 2A — Supabase Proxy

```
Rossmann Store Sales (Kaggle CSV, 1 store filtered ~12MB)
    + synthetic shelf_life_hours column (SLED equivalent)
    ↓
Supabase Postgres table: inventory_features
    ↓
Python feature computation → flat feature vector (6 fields, frozen schema above)
    ↓
XGBoost trained locally / GitHub Actions → joblib pickle
    ↓
FastAPI on Railway loads pickle at startup
POST /infer → { item_id, discount_pct, confidence, expiry_risk }
```

## Phase 2B — Databricks Medallion

```
Bronze Layer:
  BODS RFC/ODP → KONV pricing conditions (nightly batch)
  Lakeflow Connect CDC → MM-IM stock + EWM SLED (sub-minute)

Silver Layer (Freshness Ledger):
  Delta Live Tables
  join(SLED, stock_snapshot, POS_velocity, weather_signal)

Gold Layer (Recommended Price Table):
  M2 output: expiry_risk_score per SKU
  M3 output: discount_pct per SKU (exact %, e.g. 18%)

Feature Store:
  Databricks Feature Store serves features to M2 + M3 at inference
  Same 6-field schema as Phase 2A (frozen)

Model Serving:
  Databricks Model Serving REST endpoint
  Node.js BFF: POST /serving-endpoints/m3-freshness/invocations

Retraining Loop:
  Manager accept/modify → Delta Lake event
  MLflow incremental retrain
  Logged features: manager_override_flag, actual_discount_pct, units_sold_post_markdown
```

## Databricks Solution Accelerator

Base: `databricks-industry-solutions/price-optimization`

Required customisations (accelerator does NOT include these):
1. Add `shelf_life_hours` / SLED dimension (freshness-aware pricing, not just demand elasticity)
2. Replace synthetic retail data with KONV/SLED feed from SAP ECC
3. Add BAPI_PRICES_CONDITIONS write-back layer (accelerator stops at "recommended price")
4. Add BRE margin floor guardrail (discount > 50% → manager gate)

## Markdown Cases (POC: Dynamic Freshness M3 only)

| Case | ZMKD Pattern | BAPI |
|------|-------------|------|
| Dynamic Freshness (M3) — POC SCOPE | Single ZMKD | BAPI_PRICES_CONDITIONS |
| Golden Hour | Timed ZMKD (ValidFrom/ValidTo 16:00–19:00) | BAPI_PRICES_CONDITIONS |
| Markdown Ladder | 5× ZMKD pre-staged at 06:00 AM | BAPI_PRICES_CONDITIONS |
| Weather Liftup | Positive + markdown ZMKD dual | BAPI_PRICES_CONDITIONS |
| Green Leaf Premium | ZMKD tagged to Unity Catalog ESG | BAPI_PRICES_CONDITIONS |
| Bundle Intelligence | SD Bundle Condition | BAPI_SALESORDER_CREATEFROMDAT2 |
| B2B Rescue | No ZMKD (B2B revenue line) | BAPI_SALESORDER_CREATEFROMDAT2 |
| Cross-Store Transfer | No ZMKD | BAPI_GOODSMVT_CREATE |
| Loyalty (Invisible) | Member condition | SAP Loyalty Engine |
