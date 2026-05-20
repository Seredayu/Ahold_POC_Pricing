# Databricks notebook source
# Bronze layer: KONV pricing conditions via BODS RFC/ODP (DLT)
#
# KONV is a SAP cluster table — no CDC support.
# Ingestion uses BODS RFC/ODP with delta pointers (nightly batch).
#
# SAP RFC access available: 2026-05-29
# Toggle USE_SYNTHETIC = False after that date.

import dlt
import datetime
from decimal import Decimal
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DecimalType, TimestampType
)
from pyspark.sql.functions import current_timestamp, lit

USE_SYNTHETIC = True  # TODO: set False after 2026-05-29 when SAP RFC is live

KONV_SCHEMA = StructType([
    StructField("KNUMV",      StringType(),      False),
    StructField("KPOSN",      StringType(),      False),
    StructField("STUNR",      StringType(),      False),
    StructField("ZAEHK",      StringType(),      False),
    StructField("KSCHL",      StringType(),      True),
    StructField("KBETR",      DecimalType(15,2), True),
    StructField("WAERS",      StringType(),      True),
    StructField("KMEIN",      StringType(),      True),
    StructField("DATAB",      StringType(),      True),
    StructField("DATBI",      StringType(),      True),
    StructField("MATNR",      StringType(),      True),
    StructField("WERKS",      StringType(),      True),
    StructField("VKORG",      StringType(),      True),
    StructField("VTWEG",      StringType(),      True),
    StructField("_ingest_ts", TimestampType(),   True),
    StructField("_batch_date",StringType(),      True),
])


def _synthetic(batch_date: str):
    rows = []
    for i in range(1, 13):
        rows.append((
            f"00000{i:05d}", "000010", "100", "01",
            "PR00", Decimal(str(round(2.49 + i * 0.5, 2))), "EUR", "ST",
            batch_date.replace("-", ""), batch_date.replace("-", ""),
            f"SKU-{i:03d}", "BE01", "1000", "10",
            datetime.datetime.utcnow(), batch_date,
        ))
    return spark.createDataFrame(rows, schema=KONV_SCHEMA)


def _from_sap(batch_date: str):
    return (
        spark.read
        .format("com.databricks.sap")
        .option("host",           spark.conf.get("spark.databricks.sap.host"))
        .option("client",         spark.conf.get("spark.databricks.sap.client"))
        .option("systemNumber",   spark.conf.get("spark.databricks.sap.sysnr"))
        .option("user",           dbutils.secrets.get("sap-btp", "logon-user"))
        .option("password",       dbutils.secrets.get("sap-btp", "logon-password"))
        .option("odpServiceName", "0COPA_C01")
        .option("odpEntityName",  "KONV")
        .option("extractionMode", "Delta")
        .schema(KONV_SCHEMA)
        .load()
        .withColumn("_ingest_ts",   current_timestamp())
        .withColumn("_batch_date",  lit(batch_date))
    )


@dlt.table(
    name="bronze_konv_pricing",
    comment="Bronze: KONV pricing conditions from SAP ECC 6.0 via BODS RFC/ODP"
)
def bronze_konv_pricing():
    batch_date = datetime.date.today().isoformat()
    return _synthetic(batch_date) if USE_SYNTHETIC else _from_sap(batch_date)
