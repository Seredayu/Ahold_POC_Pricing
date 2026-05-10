# Data Models

## Inventory Item (React app / mockData.js)

```typescript
interface Item {
  item_id: string           // e.g. "SKU-001"
  name_fr: string           // French display name
  name_nl: string           // Dutch display name
  current_price: number     // EUR, e.g. 3.49
  stock: number             // units on shelf
  hours_to_close: number    // SLED proxy: remaining shelf life hours
  sales_velocity_7d: number // units/day rolling 7-day average
}
```

## Recommendation (decisionTable.js / Phase 2: ML inference)

```typescript
interface Recommendation {
  recommended: boolean
  discount_pct: number        // e.g. 0.40 = 40% off
  recommended_price: number   // current_price * (1 - discount_pct)
  confidence: number          // 0–1, deterministic in Phase 1
  expiry_risk: number         // 0–1
  manager_required: boolean   // true when discount_pct > 0.50
  sales_velocity_7d: number
}
```

## ML Feature Schema (FROZEN — must match Phase 2A and 2B Feature Store)

```
inventory_age_days    float   Days since GR (goods receipt)
stock_pressure        float   stock / avg_daily_sales
hour_of_day           int     0–23
sales_velocity_7d     float   units/day rolling 7d
weather_signal        float   temperature delta vs 30d avg (proxy for demand shift)
price_history_7d      float   avg price last 7 days
```

**Do not rename or add fields without updating both FastAPI (Phase 2A) and Databricks Feature Store (Phase 2B).**

## Discount Tiers (Phase 1 decision table)

| Condition | Discount |
|-----------|---------|
| hours_to_close < 4 | 40% |
| hours_to_close < 6 | 30% |
| hours_to_close < 8 | 20% |
| hours_to_close >= 8 OR stock <= 10 | No recommendation |

## API Contracts

### POST /api/approve

Request:
```json
{ "item_id": "SKU-001", "discount_pct": 0.30, "manager_override": false }
```

Response (success):
```json
{
  "status": "zmkd_queued",
  "condition_record": "0000012345",
  "condition_type": "ZMKD",
  "table": "A004",
  "discount_pct": 0.30,
  "valid_from": "2026-05-10",
  "valid_to": "2026-05-11"
}
```

Response (idempotent repeat):
```json
{ "status": "already_applied", "condition_record": null }
```

Response (BRE guardrail — discount > 50% without manager override):
```json
{ "error": "manager_approval_required", "discount_pct": 0.55 }
```

### POST /api/reject

Request:
```json
{ "item_id": "SKU-001", "reason_code": "associate_judgement" }
```

Response:
```json
{ "status": "rejected", "item_id": "SKU-001", "reason_code": "associate_judgement" }
```
