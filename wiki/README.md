# Wiki — Ahold Delhaize Dynamic Freshness Pricing POC

## Architecture

| Doc | Contents |
|-----|---------|
| [Integration Flow](architecture/integration-flow.md) | SAP ECC → Databricks → React → BAPI write-back. Phase comparison table. ZMKD schema. |
| [Data Models](architecture/data-models.md) | Item/Recommendation interfaces. Frozen ML feature schema. API contracts. Discount tiers. |
| [ML Pipeline](architecture/ml-pipeline.md) | M2/M3 model map. Phase 2A Supabase proxy. Phase 2B Databricks Medallion. 9 markdown cases. |

## Onboarding

| Doc | Contents |
|-----|---------|
| [Local Setup](onboarding/local-setup.md) | Run Phase 1 mock demo locally. BFF + Vite dev server. Endpoints. Acceptance criteria. |
| [Project Context](onboarding/project-context.md) | Business problem, wedge, phased approach, key constraints, open questions. |
