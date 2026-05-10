# Integration Flow — Ahold Delhaize Dynamic Freshness Pricing

## End-to-End Data + Action Flow

```
SAP ECC 6.0 (MM-IM / KONV)
    │
    ├─ BODS RFC/ODP (nightly delta) ──────────────────────────────────┐
    │  KONV = cluster table, cannot use CDC directly                  │
    │                                                                 ▼
    └─ Lakeflow Connect CDC (sub-minute) ──────► Databricks Bronze Layer
       MM-IM stock + EWM SLED (transparent tables only)              │
                                                                      ▼
                                                          Silver: Freshness Ledger
                                                 join(SLED, stock, POS velocity, weather)
                                                                      │
                                                                      ▼
                                                    Gold: Recommended Price Table
                                                    M2 XGBoost (expiry risk 72h)
                                                    M3 XGBoost/RL (markdown %)
                                                                      │
                                                                      ▼
                                                    React Field App (associate scans barcode)
                                                    AI recommendation → one-tap approve
                                                                      │
                                                    Node.js BFF (Azure Container Apps)
                                                                      │
                                                    SAP BTP Cloud Connector (RFC tunnel)
                                                                      │
                                                    BAPI_PRICES_CONDITIONS
                                                                      │
                                                          ┌───────────┴───────────┐
                                                          ▼                       ▼
                                                   ZMKD record              async writes
                                                   in SAP A004          S/4HANA P&L (price variance)
                                                          │             Delta Lake (retrain trigger)
                                                          ▼
                                               POS + ESL + Hybris web sync instantly
```

## Key Integration Constraints

| Component | Constraint |
|-----------|-----------|
| KONV (pricing conditions) | Cluster table — BODS RFC/ODP required, not Lakeflow CDC |
| MM-IM stock + EWM SLED | Transparent tables — Lakeflow Connect CDC, sub-minute latency |
| SAP ECC RFC access | Blocked until 2026-05-29. SAP BTP Cloud Connector required as tunnel |
| BRE guardrail | discount_pct > 0.50 → manager approval required before BAPI call |
| ESL auto-flicker | Triggered when ZMKD record lands in A004 (vendor-agnostic) |
| Belgian CAO/CCT | Works Council gate before Phase 2 go-live. Each new task must offset a legacy ECC manual task |

## ZMKD Mock Response Schema (Phase 1 → Phase 2 swap = URL change only)

```json
{
  "status": "zmkd_queued",
  "condition_record": "0000012345",
  "condition_type": "ZMKD",
  "table": "A004",
  "discount_pct": 0.18,
  "valid_from": "2026-05-10",
  "valid_to": "2026-05-11"
}
```

## Phase Architecture Comparison

| Layer | Phase 1 (Mock) | Phase 2A (Supabase proxy) | Phase 2B (Databricks Medallion) |
|-------|---------------|--------------------------|--------------------------------|
| Data | Hardcoded mockData.js | Supabase Postgres (Rossmann seed) | Databricks Lakehouse (SAP feeds) |
| ML | Decision table (if/then) | XGBoost pickle (FastAPI) | Databricks Model Serving |
| Feature store | None | Python dict | Databricks Feature Store |
| API | Express mock BFF | FastAPI on Railway | Node.js BFF on Azure Container Apps |
| Write-back | Mock ZMKD JSON | Mock ZMKD JSON | Real BAPI_PRICES_CONDITIONS via BTP |
| Frontend | Vercel | Vercel | Azure Static Web Apps |
