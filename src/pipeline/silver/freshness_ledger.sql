-- Databricks notebook source
-- Silver layer: Freshness Ledger
--
-- Joins Bronze SLED expiry dates + MM-IM stock levels + KONV pricing history
-- into a single per-SKU-per-store freshness snapshot.
--
-- Output table: silver.freshness_ledger
-- Refresh: triggered after Bronze batch completes (05:45 daily)

-- COMMAND ----------

-- Latest expiry per SKU + store
CREATE OR REFRESH LIVE VIEW sled_latest AS
SELECT
    s.MATNR                                                         AS item_id,
    s.WERKS                                                         AS store_id,
    MIN(s.VFDAT)                                                    AS earliest_expiry_date,
    DATEDIFF(HOUR, current_timestamp(),
        to_timestamp(MIN(s.VFDAT), 'yyyyMMdd'))                    AS shelf_life_hours,
    MAX(s._cdc_ts)                                                  AS last_sled_update
FROM LIVE.sled_records s
WHERE s._cdc_op != 'D'
GROUP BY s.MATNR, s.WERKS;

-- COMMAND ----------

-- Current unrestricted stock per SKU + store
CREATE OR REFRESH LIVE VIEW stock_current AS
SELECT
    m.MATNR                 AS item_id,
    m.WERKS                 AS store_id,
    SUM(m.LABST)            AS stock_qty,
    m.MEINH                 AS uom,
    MAX(m._cdc_ts)          AS last_stock_update
FROM LIVE.stock_movements m
WHERE m._cdc_op != 'D'
GROUP BY m.MATNR, m.WERKS, m.MEINH;

-- COMMAND ----------

-- Rolling 7d average price per SKU + store (base price PR00 only)
CREATE OR REFRESH LIVE VIEW pricing_history AS
SELECT
    k.MATNR                             AS item_id,
    k.WERKS                             AS store_id,
    AVG(CAST(k.KBETR AS DOUBLE))        AS price_history_mean,
    MAX(CAST(k._batch_date AS DATE))    AS last_price_update
FROM LIVE.konv_pricing k
WHERE k.KSCHL = 'PR00'
  AND CAST(k._batch_date AS DATE) >= DATE_SUB(current_date(), 7)
GROUP BY k.MATNR, k.WERKS;

-- COMMAND ----------

-- Freshness Ledger: main Silver table
-- Feature schema FROZEN — must match Phase 2A FEATURE_COLS in inference.py
CREATE OR REFRESH LIVE TABLE freshness_ledger
COMMENT "Per-SKU per-store freshness snapshot. Feature schema frozen."
TBLPROPERTIES (
    "quality" = "silver",
    "pipelines.autoOptimize.managed" = "true"
) AS
SELECT
    sl.item_id,
    sl.store_id,

    -- Display fields
    COALESCE(k.KBETR, 3.49)                                         AS current_price,
    st.stock_qty                                                     AS stock,
    sl.shelf_life_hours,

    -- FROZEN FEATURE COLUMNS
    COALESCE(
        DATEDIFF(current_date(),
            DATE_SUB(current_date(), CAST(sl.shelf_life_hours / 24 AS INT))),
        1
    )                                                                AS inventory_age_days,

    CASE
        WHEN ph.price_history_mean IS NULL OR ph.price_history_mean = 0 THEN 1.0
        ELSE st.stock_qty / ph.price_history_mean
    END                                                              AS stock_pressure,

    HOUR(current_timestamp())                                        AS hour_of_day,

    -- POS velocity: default 5.0 until POS pipeline wired (Phase 2B+)
    5.0                                                              AS sales_velocity_7d,

    -- Weather signal: default 0.5 until weather API wired (Phase 2B+)
    0.5                                                              AS weather_signal,

    COALESCE(ph.price_history_mean, 3.49)                           AS price_history_7d,

    sl.last_sled_update,
    st.last_stock_update,
    current_timestamp()                                              AS _silver_ts

FROM LIVE.sled_latest sl

JOIN LIVE.stock_current st
    ON sl.item_id = st.item_id AND sl.store_id = st.store_id

LEFT JOIN (
    SELECT MATNR, WERKS, KBETR,
           ROW_NUMBER() OVER (
               PARTITION BY MATNR, WERKS
               ORDER BY CAST(_batch_date AS DATE) DESC
           ) AS rn
    FROM LIVE.konv_pricing
    WHERE KSCHL = 'PR00'
) k ON sl.item_id = k.MATNR AND sl.store_id = k.WERKS AND k.rn = 1

LEFT JOIN LIVE.pricing_history ph
    ON sl.item_id = ph.item_id AND sl.store_id = ph.store_id

WHERE sl.shelf_life_hours IS NOT NULL
  AND sl.shelf_life_hours > 0
  AND st.stock_qty > 0;
