# Databricks notebook source
# Bronze layer: MM-IM stock movements + EWM SLED via Lakeflow Connect CDC (DLT)
#
# MM-IM (MARD) and EWM (LQUA) are transparent SAP tables — CDC valid here.
# Lakeflow Connect streams changes at sub-minute latency.
#
# SAP RFC / Lakeflow connector available: 2026-05-29
# Toggle USE_SYNTHETIC = False after that date.

import dlt
import datetime
from decimal import Decimal
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DecimalType, TimestampType
)
from pyspark.sql.functions import current_timestamp

USE_SYNTHETIC = True  # TODO: set False after 2026-05-29

STOCK_SCHEMA = StructType([
    StructField("MANDT",      StringType(),      False),
    StructField("MATNR",      StringType(),      False),
    StructField("WERKS",      StringType(),      False),
    StructField("LGORT",      StringType(),      True),
    StructField("LABST",      DecimalType(13,3), True),
    StructField("INSME",      DecimalType(13,3), True),
    StructField("EINME",      DecimalType(13,3), True),
    StructField("MEINH",      StringType(),      True),
    StructField("_cdc_op",    StringType(),      True),
    StructField("_cdc_ts",    TimestampType(),   True),
    StructField("_ingest_ts", TimestampType(),   True),
])

SLED_SCHEMA = StructType([
    StructField("MANDT",      StringType(),      False),
    StructField("LGNUM",      StringType(),      False),
    StructField("LGTYP",      StringType(),      False),
    StructField("LGPLA",      StringType(),      False),
    StructField("MATNR",      StringType(),      False),
    StructField("WERKS",      StringType(),      False),
    StructField("VFDAT",      StringType(),      True),
    StructField("ANZME",      DecimalType(13,3), True),
    StructField("MEINH",      StringType(),      True),
    StructField("_cdc_op",    StringType(),      True),
    StructField("_cdc_ts",    TimestampType(),   True),
    StructField("_ingest_ts", TimestampType(),   True),
])


def _synthetic_stock():
    now = datetime.datetime.utcnow()
    stocks = [17, 8, 24, 12, 31, 11, 14, 19, 22, 16, 18, 28]
    rows = [
        ("100", f"SKU-{i:03d}", "BE01", "0001",
         Decimal(str(s)), Decimal("0.0"), Decimal("0.0"), "ST", "I", now, now)
        for i, s in enumerate(stocks, start=1)
    ]
    return spark.createDataFrame(rows, schema=STOCK_SCHEMA)


def _synthetic_sled():
    now = datetime.datetime.utcnow()
    shelf_hours = [6, 3, 5, 7, 4, 4, 6, 6, 7, 5, 7, 3]
    stocks      = [17, 8, 24, 12, 31, 11, 14, 19, 22, 16, 18, 28]
    rows = [
        ("100", "BE01", "001", f"BIN-{i:04d}", f"SKU-{i:03d}", "BE01",
         (datetime.date.today() + datetime.timedelta(hours=h)).strftime("%Y%m%d"),
         Decimal(str(s)), "ST", "I", now, now)
        for i, (h, s) in enumerate(zip(shelf_hours, stocks), start=1)
    ]
    return spark.createDataFrame(rows, schema=SLED_SCHEMA)


@dlt.table(
    name="bronze_stock_movements",
    comment="Bronze: MM-IM stock levels per SKU/store from SAP MARD via Lakeflow CDC"
)
def bronze_stock_movements():
    if USE_SYNTHETIC:
        return _synthetic_stock()
    return (
        spark.readStream
        .format("lakeflow")
        .option("connection",     "sap-ecc-be01")
        .option("sourceTable",    "MARD")
        .option("startingVersion","latest")
        .schema(STOCK_SCHEMA)
        .load()
        .withColumn("_ingest_ts", current_timestamp())
    )


@dlt.table(
    name="bronze_sled_records",
    comment="Bronze: EWM shelf-life expiry dates per SKU/bin from SAP LQUA via Lakeflow CDC"
)
def bronze_sled_records():
    if USE_SYNTHETIC:
        return _synthetic_sled()
    return (
        spark.readStream
        .format("lakeflow")
        .option("connection",     "sap-ecc-be01")
        .option("sourceTable",    "LQUA")
        .option("startingVersion","latest")
        .schema(SLED_SCHEMA)
        .load()
        .withColumn("_ingest_ts", current_timestamp())
    )
