-- Databricks DLT notebook source
-- Silver layer: Freshness Ledger
--
-- Joins Bronze SLED expiry dates + MM-IM stock levels + KONV pricing history
-- into a single per-SKU-per-store freshness snapshot.
--
-- Output table: silver.freshness_ledger
-- Refresh: triggered after Bronze batch completes (05:45 daily)
-- SLA: Silver ready by 05:55 for Gold / M2+M3 inference at 06:00

-- COMMAND ----------
-- Configure DLT pipeline properties

-- MAGIC %python
-- MAGIC import dlt

-- COMMAND ----------

-- Base SLED view: latest expiry per SKU + store
-- shelf_life_hours = hours until earliest expiry bin hits zero
CREATE OR REPLACE LIVE VIEW sled_latest AS
SELECT
    s.MATNR                                          AS item_id,
    s.WERKS                                          AS store_id,
    MIN(s.VFDAT)                                     AS earliest_expiry_date,
    DATEDIFF(HOUR, current_timestamp(),
        to_timestamp(MIN(s.VFDAT), 'yyyyMMdd'))      AS shelf_life_hours,
    MAX(s._cdc_ts)                                   AS last_sled_update
FROM ahold_poc.bronze.sled_records s
WHERE s._cdc_op != 'D'            -- exclude CDC deletes
GROUP BY s.MATNR, s.WERKS;

-- COMMAND ----------

-- Base stock view: current unrestricted stock per SKU + store
CREATE OR REPLACE LIVE VIEW stock_current AS
SELECT
    m.MATNR                        AS item_id,
    m.WERKS                        AS store_id,
    SUM(m.LABST)                   AS stock_qty,
    m.MEINH                        AS uom,
    MAX(m._cdc_ts)                 AS last_stock_update
FROM ahold_poc.bronze.stock_movements m
WHERE m._cdc_op != 'D'
GROUP BY m.MATNR, m.WERKS, m.MEINH;

-- COMMAND ----------

-- KONV pricing history: rolling 7d average price per SKU + store
-- Filter KSCHL = 'PR00' (base price) — exclude markdown conditions here;
-- ZMKD conditions are the outputs of this pipeline, not inputs.
CREATE OR REPLACE LIVE VIEW pricing_history AS
SELECT
    k.MATNR                        AS item_id,
    k.WERKS                        AS store_id,
    AVG(CAST(k.KBETR AS DOUBLE))   AS price_history_mean,
    COLLECT_LIST(
        CAST(k.KBETR AS DOUBLE)
    )                              AS price_history_7d,
    MAX(CAST(k._batch_date AS DATE)) AS last_price_update
FROM ahold_poc.bronze.konv_pricing k
WHERE k.KSCHL = 'PR00'
  AND CAST(k._batch_date AS DATE) >= DATE_SUB(current_date(), 7)
GROUP BY k.MATNR, k.WERKS;

-- COMMAND ----------

-- Freshness Ledger: main Silver table
-- Computes all 6 frozen feature columns + display fields
CREATE OR REPLACE LIVE TABLE freshness_ledger
COMMENT "Per-SKU per-store freshness snapshot. Feature schema frozen — must match Phase 2A FEATURE_COLS."
TBLPROPERTIES (
    "quality"       = "silver",
    "pipelines.autoOptimize.managed" = "true"
) AS
SELECT
    sl.item_id,
    sl.store_id,

    -- Display fields (surfaced in React app)
    k.KBETR                             AS current_price,
    st.stock_qty                        AS stock,
    sl.shelf_life_hours,

    -- ============================================================
    -- FROZEN FEATURE COLUMNS (must match feature_pipeline.py FEATURE_COLS)
    -- Do NOT rename or reorder without updating Phase 2A + Feature Store
    -- ============================================================
    DATEDIFF(
        current_date(),
        DATE_SUB(current_date(), CAST(sl.shelf_life_hours / 24 AS INT))
    )                                   AS inventory_age_days,

    CASE
        WHEN ph.price_history_mean IS NULL OR ph.price_history_mean = 0 THEN 0.0
        ELSE CAST(k.KBETR AS DOUBLE) / ph.price_history_mean
    END                                 AS stock_pressure,

    HOUR(current_timestamp())           AS hour_of_day,

    -- sales_velocity_7d: units/day rolling 7d
    -- Sourced from POS transaction data (Delta table populated separately)
    -- Default 5.0 until POS pipeline is wired (Phase 2B+)
    COALESCE(pos.velocity_7d, 5.0)      AS sales_velocity_7d,

    -- weather_signal: 0.0–1.0 (0 = cold/rainy, 1 = hot/sunny)
    -- Sourced from external weather API (Phase 2B+ — default 0.5)
    COALESCE(wx.signal, 0.5)            AS weather_signal,

    ph.price_history_7d                 AS price_history_7d,
    ph.price_history_mean               AS price_history_mean,
    -- ============================================================

    sl.last_sled_update,
    st.last_stock_update,
    current_timestamp()                 AS _silver_ts

FROM LIVE.sled_latest sl

JOIN LIVE.stock_current st
    ON sl.item_id = st.item_id AND sl.store_id = st.store_id

-- Latest base price from KONV
LEFT JOIN (
    SELECT MATNR, WERKS, KBETR,
           ROW_NUMBER() OVER (
               PARTITION BY MATNR, WERKS
               ORDER BY CAST(_batch_date AS DATE) DESC
           ) AS rn
    FROM ahold_poc.bronze.konv_pricing
    WHERE KSCHL = 'PR00'
) k ON sl.item_id = k.MATNR AND sl.store_id = k.WERKS AND k.rn = 1

LEFT JOIN LIVE.pricing_history ph
    ON sl.item_id = ph.item_id AND sl.store_id = ph.store_id

-- POS velocity (populated by separate POS ingest job — Phase 2B+)
LEFT JOIN ahold_poc.silver.pos_velocity pos
    ON sl.item_id = pos.item_id AND sl.store_id = pos.store_id

-- Weather signal (populated by weather API job — Phase 2B+)
LEFT JOIN ahold_poc.silver.weather_signals wx
    ON sl.store_id = wx.store_id
    AND CAST(wx.forecast_date AS DATE) = current_date()

WHERE sl.shelf_life_hours IS NOT NULL
  AND sl.shelf_life_hours > 0
  AND st.stock_qty > 0;
