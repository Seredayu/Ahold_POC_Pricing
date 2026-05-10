# Project Context — Ahold Delhaize Dynamic Freshness Pricing POC

## Problem

Store managers manually review ~1,000 order lines daily (06:00–08:00). Fresh produce pricing uses static min/max rules. Result: €200M+ annual perishable waste, €350M+ EBITDA opportunity untapped.

## Wedge

One full-loop dynamic pricing trigger:

1. AI recommends markdown for near-expiry item
2. Store associate approves via React Field App (one tap)
3. ZMKD condition record created in SAP ECC 6.0 via `BAPI_PRICES_CONDITIONS`
4. ESL (electronic shelf label) updates automatically

Physical ESL label change = highest-demo-impact artifact for sponsor acquisition.

## Why This Approach

- Mock demo first (Phase 1, weeks 1–2): no ML, no SAP access needed, can demo in 2 weeks
- Real ML + synthetic data (Phase 2A, weeks 3–6): Supabase + FastAPI proxy
- Databricks Medallion + real SAP feeds (Phase 2B, weeks 7–12): post-sponsor, post-RFC access
- Sponsor IS the product. The code is just the evidence.

## Key Constraints

| Constraint | Detail |
|-----------|--------|
| SAP RFC access | Blocked until 2026-05-29. Requires IT contact for SAP BTP Cloud Connector |
| Belgian CAO/CCT | Works Council gate before Phase 2 go-live |
| CSRD compliance | ESG audit trail auto-populated via ZMKD tagging |
| KONV extraction | Cluster table → BODS only, not Lakeflow CDC |
| Bilingual | All user-facing strings in FR (default) + NL (Belgium Delhaize stores) |

## Open Questions

1. Which Belgium Delhaize IT contact owns SAP BTP Cloud Connector subaccount?
2. Which stores use which ESL vendor (Pricer / SES-imagotag / Solum)?
3. Is there a named internal sponsor?
4. What is the Works Council review timeline for Phase 2?

## POC Scope

Dynamic Freshness (M3) only. All other markdown cases (Golden Hour, Markdown Ladder, Bundle Intelligence, etc.) are Phase 3+.
