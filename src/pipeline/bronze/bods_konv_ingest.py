# Databricks notebook source
# Bronze layer: KONV pricing conditions via BODS RFC/ODP
#
# KONV is a SAP cluster table — no CDC support.
# Ingestion uses BODS RFC/ODP with delta pointers (nightly batch).
#
# SAP RFC access available: 2026-05-29
# Until then: synthetic data generator at bottom of file (toggle USE_SYNTHETIC).
#
# Target table: bronze.konv_pricing (Delta, Unity Catalog)
# Schedule: daily 05:30 (before stores open at 06:00)

# COMMAND ----------

USE_SYNTHETIC = True  # TODO: set False after 2026-05-29 when SAP RFC is live

CATALOG = "ahold_poc"
SCHEMA  = "bronze"
TABLE   = f"{CATALOG}.{SCHEMA}.konv_pricing"

# COMMAND ----------
# MAGIC %sql
# MAGIC CREATE CATALOG IF NOT EXISTS ahold_poc;
# MAGIC CREATE SCHEMA IF NOT EXISTS ahold_poc.bronze;

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DecimalType, IntegerType, TimestampType
)
from pyspark.sql.functions import current_timestamp, lit
from delta.tables import DeltaTable
import datetime

spark = SparkSession.builder.getOrCreate()

# KONV schema (relevant fields for markdown pricing)
# Full cluster table has 100+ fields — we project only what M2/M3 need.
KONV_SCHEMA = StructType([
    StructField("KNUMV",   StringType(),   False),  # condition record number
    StructField("KPOSN",   StringType(),   False),  # condition item
    StructField("STUNR",   StringType(),   False),  # step number
    StructField("ZAEHK",   StringType(),   False),  # counter
    StructField("KSCHL",   StringType(),   True),   # condition type (ZMKD = markdown)
    StructField("KBETR",   DecimalType(15,2), True),# condition value (price / %)
    StructField("WAERS",   StringType(),   True),   # currency
    StructField("KMEIN",   StringType(),   True),   # condition unit
    StructField("DATAB",   StringType(),   True),   # valid from (YYYYMMDD)
    StructField("DATBI",   StringType(),   True),   # valid to (YYYYMMDD)
    StructField("MATNR",   StringType(),   True),   # material number (SKU)
    StructField("WERKS",   StringType(),   True),   # plant (store)
    StructField("VKORG",   StringType(),   True),   # sales org
    StructField("VTWEG",   StringType(),   True),   # distribution channel
    StructField("_ingest_ts", TimestampType(), True),  # bronze watermark
    StructField("_batch_date", StringType(), True),    # batch run date
])

# COMMAND ----------

def ingest_from_sap(batch_date: str) -> "DataFrame":
    """
    RFC/ODP extraction from SAP ECC 6.0 KONV table.
    Uses Databricks SAP connector (com.databricks.sap) with ODP source.

    TODO: activate after 2026-05-29
    Requires:
      - spark.conf set spark.databricks.sap.host       <BTP_HOST>
      - spark.conf set spark.databricks.sap.client     <SAP_CLIENT>
      - spark.conf set spark.databricks.sap.sysnr      <SYSTEM_NUMBER>
      - Databricks secret: sap-logon-user, sap-logon-password
      - SAP BTP Cloud Connector tunnel configured (infra/btp/)
    """
    # ODP context for pricing conditions table
    return (
        spark.read
        .format("com.databricks.sap")
        .option("host",        spark.conf.get("spark.databricks.sap.host"))
        .option("client",      spark.conf.get("spark.databricks.sap.client"))
        .option("systemNumber",spark.conf.get("spark.databricks.sap.sysnr"))
        .option("user",        dbutils.secrets.get("sap-btp", "logon-user"))
        .option("password",    dbutils.secrets.get("sap-btp", "logon-password"))
        .option("odpServiceName", "0COPA_C01")   # ODP service for KONV
        .option("odpEntityName",  "KONV")
        .option("extractionMode", "Delta")
        .option("deltaToken",  _read_delta_token())
        .schema(KONV_SCHEMA)
        .load()
        .withColumn("_ingest_ts",  current_timestamp())
        .withColumn("_batch_date", lit(batch_date))
    )


def ingest_synthetic(batch_date: str) -> "DataFrame":
    """Synthetic KONV data mirroring the 12 Belgium Delhaize demo items."""
    import random
    rows = []
    skus = [f"SKU-{i:03d}" for i in range(1, 13)]
    for i, sku in enumerate(skus):
        rows.append((
            f"00000{i+1:05d}",  # KNUMV
            "000010",            # KPOSN
            "100",               # STUNR
            "01",                # ZAEHK
            "PR00",              # KSCHL (base price)
            float(2.49 + i * 0.5),  # KBETR
            "EUR",               # WAERS
            "ST",                # KMEIN
            batch_date.replace("-", ""),  # DATAB
            batch_date.replace("-", ""),  # DATBI
            sku,                 # MATNR
            "BE01",              # WERKS (Belgium pilot store)
            "1000",              # VKORG
            "10",                # VTWEG
            datetime.datetime.utcnow(),  # _ingest_ts
            batch_date,          # _batch_date
        ))
    return spark.createDataFrame(rows, schema=KONV_SCHEMA)


def _read_delta_token() -> str:
    """Read last successful ODP delta token from Delta table watermark."""
    try:
        row = spark.sql(
            f"SELECT max(_odp_delta_token) FROM {TABLE} WHERE KSCHL='ZMKD'"
        ).collect()[0][0]
        return row or ""
    except Exception:
        return ""  # full load on first run


# COMMAND ----------

batch_date = datetime.date.today().isoformat()

if USE_SYNTHETIC:
    print(f"[SYNTHETIC] Generating KONV data for {batch_date}")
    df = ingest_synthetic(batch_date)
else:
    print(f"[SAP RFC] Extracting KONV delta for {batch_date}")
    df = ingest_from_sap(batch_date)

print(f"Rows fetched: {df.count()}")

# COMMAND ----------
# Upsert into Bronze Delta table (merge on KNUMV + KPOSN + STUNR + ZAEHK)

if DeltaTable.isDeltaTable(spark, TABLE):
    dt = DeltaTable.forName(spark, TABLE)
    (
        dt.alias("target")
        .merge(
            df.alias("source"),
            "target.KNUMV = source.KNUMV AND target.KPOSN = source.KPOSN "
            "AND target.STUNR = source.STUNR AND target.ZAEHK = source.ZAEHK"
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
else:
    df.write.format("delta").mode("overwrite").saveAsTable(TABLE)

print(f"Bronze KONV upsert complete -> {TABLE}")
spark.sql(f"SELECT KSCHL, COUNT(*) n FROM {TABLE} GROUP BY KSCHL").show()
