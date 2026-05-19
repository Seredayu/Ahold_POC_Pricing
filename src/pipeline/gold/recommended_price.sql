-- Databricks DLT notebook source
-- Gold layer: Recommended Price Table
--
-- Calls Databricks Model Serving (M2 + M3) via SQL AI_QUERY function.
-- Writes final recommendations to gold.recommended_price.
--
-- This table is the source-of-truth for the React Field App.
-- React app reads from here; FastAPI inference is a sidecar for Phase 2A only.
--
-- Output table: gold.recommended_price
-- Refresh: after Silver freshness_ledger updates (~06:00 daily)
-- Retention: 1 day (recommendations expire when SLED window closes)

-- COMMAND ----------
-- MAGIC %python
-- MAGIC import dlt

-- COMMAND ----------

-- M2 expiry risk score: call Databricks Model Serving endpoint
-- Model registered as: models:/m2-expiry-risk/Production
-- AI_QUERY wrapper makes the REST call inside DLT SQL
CREATE OR REPLACE LIVE VIEW m2_scores AS
SELECT
    fl.item_id,
    fl.store_id,
    fl.inventory_age_days,
    fl.stock_pressure,
    fl.hour_of_day,
    fl.sales_velocity_7d,
    fl.weather_signal,
    fl.price_history_mean,
    fl.current_price,
    fl.stock,
    fl.shelf_life_hours,

    -- M2 inference: expiry risk probability
    CAST(
        AI_QUERY(
            'ahold-m2-expiry-risk',
            NAMED_STRUCT(
                'inventory_age_days', fl.inventory_age_days,
                'stock_pressure',     fl.stock_pressure,
                'hour_of_day',        fl.hour_of_day,
                'sales_velocity_7d',  fl.sales_velocity_7d,
                'weather_signal',     fl.weather_signal,
                'price_history_mean', fl.price_history_mean
            )
        ) AS DOUBLE
    )                           AS expiry_risk

FROM ahold_poc.silver.freshness_ledger fl
WHERE fl.shelf_life_hours < 8  -- only items in the markdown window;

-- COMMAND ----------

-- M3 discount % recommendation
CREATE OR REPLACE LIVE VIEW m3_scores AS
SELECT
    m2.item_id,
    m2.store_id,
    m2.expiry_risk,
    m2.current_price,
    m2.stock,
    m2.shelf_life_hours,
    m2.sales_velocity_7d,

    -- M3 inference: discount % (clamped 0.0–0.5 in model serving wrapper)
    CAST(
        AI_QUERY(
            'ahold-m3-discount-pct',
            NAMED_STRUCT(
                'inventory_age_days', m2.inventory_age_days,
                'stock_pressure',     m2.stock_pressure,
                'hour_of_day',        m2.hour_of_day,
                'sales_velocity_7d',  m2.sales_velocity_7d,
                'weather_signal',     m2.weather_signal,
                'price_history_mean', m2.price_history_mean,
                'expiry_risk',        m2.expiry_risk
            )
        ) AS DOUBLE
    )                           AS discount_pct_raw

FROM LIVE.m2_scores m2;

-- COMMAND ----------

-- Gold: final recommended price table
-- Applies BRE guardrails and formats for React app consumption
CREATE OR REPLACE LIVE TABLE recommended_price
COMMENT "Final markdown recommendations per SKU per store. Source for React Field App."
TBLPROPERTIES (
    "quality"            = "gold",
    "delta.logRetentionDuration" = "interval 1 days",
    "pipelines.autoOptimize.managed" = "true"
) AS
SELECT
    m3.item_id,
    m3.store_id,
    m3.current_price,
    m3.stock,
    m3.shelf_life_hours                                     AS hours_to_close,
    m3.sales_velocity_7d,
    m3.expiry_risk,

    -- Clamp discount to [0.0, 0.5] — BRE hard floor
    LEAST(GREATEST(m3.discount_pct_raw, 0.0), 0.5)         AS discount_pct,

    -- Recommended price
    ROUND(
        m3.current_price * (1 - LEAST(GREATEST(m3.discount_pct_raw, 0.0), 0.5)),
        2
    )                                                       AS recommended_price,

    -- Confidence: M2 probability mapped to [0.60, 0.99]
    ROUND(LEAST(0.60 + m3.expiry_risk * 0.39, 0.99), 2)    AS confidence,

    -- BRE flags
    CASE WHEN m3.discount_pct_raw > 0.5 THEN TRUE
         ELSE FALSE END                                     AS manager_required,

    -- Only surface items with meaningful discount
    CASE WHEN LEAST(GREATEST(m3.discount_pct_raw, 0.0), 0.5) >= 0.05
         THEN TRUE ELSE FALSE END                           AS recommended,

    current_timestamp()                                     AS _gold_ts,
    DATE(current_timestamp())                               AS recommendation_date

FROM LIVE.m3_scores m3
WHERE m3.discount_pct_raw IS NOT NULL;
