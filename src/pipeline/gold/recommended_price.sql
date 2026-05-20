-- Databricks notebook source
-- Gold layer: Recommended Price Table
--
-- Phase 2B: calls Databricks Model Serving via AI_QUERY (M2 + M3).
-- Until models are deployed to Model Serving, uses Phase 1 decision table
-- logic as a drop-in approximation (same discount tiers, same output schema).
--
-- To activate real models: register m2.pkl + m3.pkl to Databricks Model Serving
-- as 'ahold-m2-expiry-risk' and 'ahold-m3-discount-pct', then replace
-- the CASE expressions below with AI_QUERY calls.
--
-- Output table: gold.recommended_price
-- Refresh: after silver.freshness_ledger updates (~06:00 daily)

-- COMMAND ----------

-- Expiry risk score (M2 approximation via decision table until Model Serving deployed)
CREATE LIVE VIEW m2_scores AS
SELECT
    fl.item_id,
    fl.store_id,
    fl.inventory_age_days,
    fl.stock_pressure,
    fl.hour_of_day,
    fl.sales_velocity_7d,
    fl.weather_signal,
    fl.price_history_7d         AS price_history_mean,
    fl.current_price,
    fl.stock,
    fl.shelf_life_hours,

    -- M2 placeholder: map shelf_life_hours to expiry_risk [0.0–1.0]
    -- Replace with: CAST(AI_QUERY('ahold-m2-expiry-risk', ...) AS DOUBLE)
    -- after model is registered in Databricks Model Serving.
    CASE
        WHEN fl.shelf_life_hours < 4 THEN 0.95
        WHEN fl.shelf_life_hours < 6 THEN 0.75
        WHEN fl.shelf_life_hours < 8 THEN 0.55
        ELSE 0.20
    END                         AS expiry_risk

FROM LIVE.silver_freshness_ledger fl
WHERE fl.shelf_life_hours < 8;

-- COMMAND ----------

-- Discount % recommendation (M3 approximation via decision table)
CREATE LIVE VIEW m3_scores AS
SELECT
    m2.item_id,
    m2.store_id,
    m2.expiry_risk,
    m2.current_price,
    m2.stock,
    m2.shelf_life_hours,
    m2.sales_velocity_7d,
    m2.inventory_age_days,
    m2.stock_pressure,
    m2.hour_of_day,
    m2.weather_signal,
    m2.price_history_mean,

    -- M3 placeholder: map expiry_risk to discount_pct
    -- Replace with: CAST(AI_QUERY('ahold-m3-discount-pct', ...) AS DOUBLE)
    -- after model is registered in Databricks Model Serving.
    CASE
        WHEN m2.expiry_risk >= 0.90 THEN 0.40
        WHEN m2.expiry_risk >= 0.70 THEN 0.30
        WHEN m2.expiry_risk >= 0.50 THEN 0.20
        ELSE 0.05
    END                         AS discount_pct_raw

FROM LIVE.m2_scores m2;

-- COMMAND ----------

-- Gold: final recommended price table with BRE guardrails
CREATE OR REFRESH LIVE TABLE recommended_price
COMMENT "Final markdown recommendations per SKU per store. Source for React Field App."
TBLPROPERTIES (
    "quality"                        = "gold",
    "delta.logRetentionDuration"     = "interval 1 days",
    "pipelines.autoOptimize.managed" = "true"
) AS
SELECT
    m3.item_id,
    m3.store_id,
    m3.current_price,
    m3.stock,
    m3.shelf_life_hours                                             AS hours_to_close,
    m3.sales_velocity_7d,
    m3.expiry_risk,

    LEAST(GREATEST(m3.discount_pct_raw, 0.0), 0.5)                 AS discount_pct,

    ROUND(
        m3.current_price * (1 - LEAST(GREATEST(m3.discount_pct_raw, 0.0), 0.5)),
        2
    )                                                               AS recommended_price,

    ROUND(LEAST(0.60 + m3.expiry_risk * 0.39, 0.99), 2)           AS confidence,

    CASE WHEN m3.discount_pct_raw > 0.5
         THEN TRUE ELSE FALSE END                                   AS manager_required,

    CASE WHEN LEAST(GREATEST(m3.discount_pct_raw, 0.0), 0.5) >= 0.05
         THEN TRUE ELSE FALSE END                                   AS recommended,

    current_timestamp()                                             AS _gold_ts,
    DATE(current_timestamp())                                       AS recommendation_date

FROM LIVE.m3_scores m3
WHERE m3.discount_pct_raw IS NOT NULL;
