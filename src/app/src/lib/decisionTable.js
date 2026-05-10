/**
 * Phase 1 hardcoded decision table.
 * Replaced in Phase 2A by FastAPI XGBoost inference.
 *
 * Rule: if hours_to_close < 8 AND stock > 10 → recommend markdown
 * Discount tiers: <4h → 40%, <6h → 30%, else → 20%
 *
 * Feature schema (FROZEN — must match Phase 2A/2B Feature Store):
 *   inventory_age_days, stock_pressure, hour_of_day,
 *   sales_velocity_7d, weather_signal, price_history_7d
 */

export function getRecommendation(item) {
  const { hours_to_close, stock, current_price, sales_velocity_7d = 4 } = item

  if (hours_to_close >= 8 || stock <= 10) {
    return { recommended: false }
  }

  const discount_pct = discountTier(hours_to_close)
  const confidence = computeConfidence(hours_to_close, stock)
  const expiry_risk = computeExpiryRisk(hours_to_close, stock)
  const recommended_price = +(current_price * (1 - discount_pct)).toFixed(2)
  const manager_required = discount_pct > 0.5

  return {
    recommended: true,
    discount_pct,
    recommended_price,
    confidence,
    expiry_risk,
    manager_required,
    sales_velocity_7d,
  }
}

function discountTier(hours) {
  if (hours < 4) return 0.40
  if (hours < 6) return 0.30
  return 0.20
}

function computeConfidence(hours, stock) {
  // Deterministic — same inputs always yield same confidence.
  const urgency = Math.min((8 - hours) / 8, 1)
  const pressure = Math.min(stock / 25, 1)
  const raw = 0.60 + urgency * 0.28 + pressure * 0.12
  return +Math.min(raw, 0.99).toFixed(2)
}

function computeExpiryRisk(hours, stock) {
  const h = Math.min((8 - hours) / 8, 1)
  const s = Math.min(stock / 30, 1)
  return +Math.min(h * 0.6 + s * 0.4, 0.99).toFixed(2)
}
