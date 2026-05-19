# Databricks notebook source
# Bronze layer: MM-IM stock movements + EWM SLED via Lakeflow Connect CDC
#
# MM-IM (Materials Management - Inventory Management) and EWM (Extended Warehouse
# Management) are transparent SAP tables — CDC is valid here, unlike KONV.
#
# Lakeflow Connect streams changes sub-minute latency.
# SAP RFC access / Lakeflow connector available: 2026-05-29
# Until then: synthetic streaming simulation (toggle USE_SYNTHETIC).
#
# Target tables:
#   bronze.stock_movements   (MM-IM MSEG / MARD)
#   bronze.sled_records      (EWM LGPLA / LTAP SLED field)

# COMMAND ----------

USE_SYNTHETIC = True  # TODO: set False after 2026-05-29

CATALOG = "ahold_poc"
SCHEMA  = "bronze"
STOCK_TABLE = f"{CATALOG}.{SCHEMA}.stock_movements"
SLED_TABLE  = f"{CATALOG}.{SCHEMA}.sled_records"

# COMMAND ----------
# MAGIC %sql
# MAGIC CREATE CATALOG IF NOT EXISTS ahold_poc;
# MAGIC CREATE SCHEMA IF NOT EXISTS ahold_poc.bronze;

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField,
    StringType, IntegerType, DecimalType, TimestampType
)
from pyspark.sql.functions import current_timestamp, lit, expr
import datetime

spark = SparkSession.builder.getOrCreate()

STOCK_SCHEMA = StructType([
    StructField("MANDT",   StringType(),      False),  # client
    StructField("MATNR",   StringType(),      False),  # material (SKU)
    StructField("WERKS",   StringType(),      False),  # plant (store)
    StructField("LGORT",   StringType(),      True),   # storage location
    StructField("LABST",   DecimalType(13,3), True),   # unrestricted stock qty
    StructField("INSME",   DecimalType(13,3), True),   # quality inspection stock
    StructField("EINME",   DecimalType(13,3), True),   # restricted use stock
    StructField("MEINH",   StringType(),      True),   # base unit of measure
    StructField("_cdc_op",     StringType(),  True),   # I/U/D from Lakeflow CDC
    StructField("_cdc_ts",     TimestampType(), True), # CDC event timestamp
    StructField("_ingest_ts",  TimestampType(), True), # bronze watermark
])

SLED_SCHEMA = StructType([
    StructField("MANDT",    StringType(),      False),
    StructField("LGNUM",    StringType(),      False),  # warehouse number
    StructField("LGTYP",    StringType(),      False),  # storage type
    StructField("LGPLA",    StringType(),      False),  # storage bin
    StructField("MATNR",    StringType(),      False),  # material (SKU)
    StructField("WERKS",    StringType(),      False),  # plant (store)
    StructField("VFDAT",    StringType(),      True),   # shelf life expiry (YYYYMMDD)
    StructField("ANZME",    DecimalType(13,3), True),   # quantity
    StructField("MEINH",    StringType(),      True),   # UoM
    StructField("_cdc_op",     StringType(),  True),
    StructField("_cdc_ts",     TimestampType(), True),
    StructField("_ingest_ts",  TimestampType(), True),
])

# COMMAND ----------

def stream_from_lakeflow_stock():
    """
    Lakeflow Connect CDC stream from SAP MM-IM (MARD table).

    TODO: activate after 2026-05-29
    Requires Lakeflow SAP CDC connector configured in Databricks workspace:
      - Connection: sap-ecc-be01 (created in Databricks Connections UI)
      - Source object: MARD (stock levels by storage location)
    """
    return (
        spark.readStream
        .format("lakeflow")
        .option("connection", "sap-ecc-be01")
        .option("sourceTable", "MARD")
        .option("startingVersion", "latest")
        .schema(STOCK_SCHEMA)
        .load()
        .withColumn("_ingest_ts", current_timestamp())
    )


def stream_from_lakeflow_sled():
    """
    Lakeflow Connect CDC stream from SAP EWM (shelf life expiry dates).
    EWM table LGPLA/LTAP contains VFDAT (Verfallsdatum = expiry date).

    TODO: activate after 2026-05-29
    """
    return (
        spark.readStream
        .format("lakeflow")
        .option("connection", "sap-ecc-be01")
        .option("sourceTable", "LQUA")   # WM quant table with VFDAT
        .option("startingVersion", "latest")
        .schema(SLED_SCHEMA)
        .load()
        .withColumn("_ingest_ts", current_timestamp())
    )


def synthetic_stock_batch():
    """Synthetic MM-IM stock snapshot matching 12 Belgium demo items."""
    now = datetime.datetime.utcnow()
    rows = [
        ("100", f"SKU-{i:03d}", "BE01", "0001",
         float(stock), 0.0, 0.0, "ST", "I", now, now)
        for i, stock in enumerate(
            [17, 8, 24, 12, 31, 11, 14, 19, 22, 16, 18, 28], start=1
        )
    ]
    return spark.createDataFrame(rows, schema=STOCK_SCHEMA)


def synthetic_sled_batch():
    """Synthetic EWM SLED records: shelf_life_hours mapped to expiry dates."""
    import datetime as dt
    now = dt.datetime.utcnow()
    shelf_hours = [6, 3, 5, 7, 4, 4, 6, 6, 7, 5, 7, 3]
    rows = [
        ("100", "BE01", "001", f"BIN-{i:04d}", f"SKU-{i:03d}", "BE01",
         (dt.date.today() + dt.timedelta(hours=h)).strftime("%Y%m%d"),
         float(stock), "ST", "I", now, now)
        for i, (h, stock) in enumerate(
            zip(shelf_hours, [17,8,24,12,31,11,14,19,22,16,18,28]), start=1
        )
    ]
    return spark.createDataFrame(rows, schema=SLED_SCHEMA)


# COMMAND ----------

if USE_SYNTHETIC:
    print("[SYNTHETIC] Writing stock snapshot ...")
    stock_df = synthetic_stock_batch()
    stock_df.write.format("delta").mode("overwrite").saveAsTable(STOCK_TABLE)

    print("[SYNTHETIC] Writing SLED snapshot ...")
    sled_df = synthetic_sled_batch()
    sled_df.write.format("delta").mode("overwrite").saveAsTable(SLED_TABLE)

    print(f"Stock rows: {spark.table(STOCK_TABLE).count()}")
    print(f"SLED rows:  {spark.table(SLED_TABLE).count()}")

else:
    # Streaming write — append-only Delta, downstream DLT reads with readStream
    print("[LAKEFLOW] Starting stock CDC stream ...")
    (
        stream_from_lakeflow_stock()
        .writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"/Volumes/{CATALOG}/bronze/checkpoints/stock")
        .toTable(STOCK_TABLE)
    )

    print("[LAKEFLOW] Starting SLED CDC stream ...")
    (
        stream_from_lakeflow_sled()
        .writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"/Volumes/{CATALOG}/bronze/checkpoints/sled")
        .toTable(SLED_TABLE)
    )
