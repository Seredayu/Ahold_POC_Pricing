# Architecture Decisions — Ahold Delhaize Dynamic Freshness Pricing

## ADR-001: Three-phase delivery strategy

**Date:** 2026-05-10 | **Status:** Active

**Decision:** Phase 1 (mock BFF, hardcoded data) → Phase 2A (real ML + Supabase) → Phase 2B (real SAP + Databricks).

**Rationale:** Derisks demo feedback loop from technical integration complexity. Phase 1 deploys and shows stakeholders before SAP RFC access is available (2026-05-29).

---

## ADR-002: Feature schema frozen across all phases

**Date:** 2026-05-10 | **Status:** Active

**Decision:** Six features locked — `inventory_age_days, stock_pressure, hour_of_day, sales_velocity_7d, weather_signal, price_history_7d`.

**Rationale:** Same schema must work in Phase 1 Python dict, Phase 2A FastAPI, and Phase 2B Databricks Feature Store. Field drift breaks model compatibility across phase boundaries.

**Constraint:** Do not add or rename fields without updating all three: `src/app/src/lib/decisionTable.js`, `src/ml/inference.py`, and Databricks Feature Store.

---

## ADR-003: ZMKD write-back response shape frozen

**Date:** 2026-05-10 | **Status:** Active

**Decision:** Response contract `{status, condition_record, condition_type, table, discount_pct, valid_from, valid_to}` is shared between mock Phase 2A and real Phase 2B BAPI call.

**Rationale:** Phase 1→2B swap is a URL/env var change only. Frontend parsing code must not change between phases.

---

## ADR-004: Supabase for Phase 2A data layer

**Date:** 2026-05-10 | **Status:** Active

**Decision:** Supabase Postgres (seeded with Rossmann dataset, 12 Belgium demo items) instead of Databricks for Phase 2A.

**Rationale:** Simpler to operate for POC before Databricks workspace is provisioned. No premium Databricks license required for Phase 2A demo validation.

---

## ADR-005: KONV ingestion via BODS RFC/ODP only (no CDC)

**Date:** 2026-05-10 | **Status:** Active

**Decision:** KONV pricing conditions table uses BODS RFC/ODP nightly batch. Lakeflow CDC explicitly excluded.

**Rationale:** KONV is a SAP cluster table (not a transparent table). Lakeflow Connect CDC requires transparent tables. Architecture is locked by SAP table type — not a product choice.

---

## ADR-006: MM-IM and EWM SLED via Lakeflow Connect CDC

**Date:** 2026-05-10 | **Status:** Active

**Decision:** MM-IM stock movements (`MARD`) and EWM SLED shelf-life records (`LQUA`) use Lakeflow Connect CDC (sub-minute latency).

**Rationale:** Both are transparent tables; CDC is available. Sub-minute freshness is required for real-time markdown decisions at store level.

---

## ADR-007: USE_SYNTHETIC toggle in Bronze notebooks

**Date:** 2026-05-13 | **Status:** Active — flip to False on 2026-05-29

**Decision:** Bronze ingestion notebooks (`bods_konv_ingest.py`, `lakeflow_stock_ingest.py`) use `USE_SYNTHETIC = True` flag that generates synthetic data mimicking 12 Belgium demo items.

**Rationale:** Enables pipeline testing and demo without live SAP connection. Single boolean minimizes go-live risk. Flip to `False` on 2026-05-29 when SAP RFC access is granted.

---

## ADR-008: BTP_ENABLED gate in Node.js BFF

**Date:** 2026-05-13 | **Status:** Active

**Decision:** `BTP_ENABLED` env var in `src/api/server.js` switches between mock ZMKD response (Phase 2A, `false`) and real `BAPI_PRICES_CONDITIONS` call via SAP BTP Cloud Connector (Phase 2B, `true`).

**Rationale:** Same BFF binary works in both phases. Go-live is an Azure Container Apps environment variable change, not a redeployment.

---

## ADR-009: Confidence score formula maps M2 probability to [0.60, 0.99]

**Date:** 2026-05-13 | **Status:** Active

**Decision:** `confidence = min(0.60 + expiry_risk * 0.39, 0.99)` in `inference.py`.

**Rationale:** Phase 1 UI assumes confidence is always meaningful (never near 0). M2 XGBoost probability (0→1) mapped to [0.60, 0.99] to preserve Phase 1 UX expectations without frontend changes. Associates see a trust signal, not a raw probability.

---

## ADR-010: Anthropic routing/orchestrator deferred to Phase 3

**Date:** 2026-05-13 | **Status:** Active — revisit after Phase 2B complete

**Decision:** No routing or orchestrator-workers pattern in Phase 1 or Phase 2. Trigger for introducing it: Phase 2B complete with 8+ active markdown case types across multiple stores.

**Rationale:** Phase 2 is single-agent (one model, one recommendation per item). Routing adds complexity without benefit at current POC scale. Phase 3 multi-store, multi-category scale justifies a routing layer.

---

## ADR-011: Belgian CAO/CCT Works Council gate

**Date:** 2026-05-10 | **Status:** Active — approval not yet received

**Decision:** Phase 2 go-live blocked until Works Council approval. Each new automated task must offset a legacy manual ECC task.

**Rationale:** Belgian labor law (CAO/CCT) requires Works Council consultation before introducing automated decision systems that affect work content. Non-negotiable legal requirement.

---

## ADR-012: SAP BTP Cloud Connector as RFC tunnel

**Date:** 2026-05-10 | **Status:** Active

**Decision:** SAP ECC RFC traffic routed through SAP BTP Cloud Connector installed on-premise. Virtual host `ecc-be.internal:3300` mapped to real SAP app server. Destination `ECC-RFC-BE` configured in BTP subaccount `eu10.hana.ondemand.com`.

**Rationale:** No direct RFC port exposure to the internet. BTP Cloud Connector is SAP's standard secure tunnel pattern for hybrid cloud integration.

---

## ADR-013: uv for Python dependency management in src/ml

**Date:** 2026-05-13 | **Status:** Active

**Decision:** `uv` manages the Python venv for `src/ml/`. Install packages with `uv pip install`, not pip directly.

**Rationale:** uv-managed venv at `.venv/Scripts/` does not include `pip.exe`. Attempting `pip install` fails silently. `uv pip install -r requirements.txt` is the correct invocation.

---

## ADR-014: hours_to_close field remapped at API boundary

**Date:** 2026-05-13 | **Status:** Active

**Decision:** `inference.py` maps Supabase field `shelf_life_hours` → API response field `hours_to_close`.

**Rationale:** React app uses `hours_to_close` (Phase 1 convention from `mockData.js`). Supabase schema uses `shelf_life_hours` (Rossmann dataset naming). Remap at the API layer avoids breaking the frontend or the Supabase schema.
