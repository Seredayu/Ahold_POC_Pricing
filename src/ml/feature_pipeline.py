"""
feature_pipeline.py — Query Supabase `inventory_features` and return a
6-column feature matrix ready for XGBoost training.

Uses the PostgREST REST API directly (httpx) because supabase-py 2.x
validates keys as JWTs, which rejects Supabase's newer `sb_publishable_*`
/ `sb_secret_*` key format introduced in 2025.

Public API
----------
    load_features() -> tuple[pd.DataFrame, pd.Series, pd.Series]
        X          : DataFrame with 6 frozen feature columns, indexed by item_id
        y_expiry   : binary Series (1 if shelf_life_hours < 6, else 0)
        y_discount : synthetic discount target clamped to [0.0, 0.5]

Usage (CLI)
-----------
    cd src/ml
    python feature_pipeline.py
"""

import os
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Frozen feature column order — must stay identical across Phase 1/2A/2B
FEATURE_COLS = [
    "inventory_age_days",
    "stock_pressure",
    "hour_of_day",
    "sales_velocity_7d",
    "weather_signal",
    "price_history_mean",   # derived from JSONB price_history_7d
]


def _load_env() -> tuple[str, str]:
    """Load .env from the same directory as this file and return (url, key)."""
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    return url, key


def _fetch_rows(url: str, key: str) -> list[dict]:
    """Fetch all rows from inventory_features via PostgREST."""
    endpoint = f"{url.rstrip('/')}/rest/v1/inventory_features"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(endpoint, headers=headers, params={"select": "*"})
    if response.status_code != 200:
        raise RuntimeError(
            f"Supabase query failed — HTTP {response.status_code}: {response.text}"
        )
    return response.json()


def load_features() -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Query Supabase inventory_features and return feature matrix + labels.

    Returns
    -------
    X : pd.DataFrame
        Shape (n_items, 6). Columns: inventory_age_days, stock_pressure,
        hour_of_day, sales_velocity_7d, weather_signal, price_history_mean.
        Index: item_id.
    y_expiry : pd.Series
        Binary label — 1 if shelf_life_hours < 6, else 0.  (M2 classifier)
    y_discount : pd.Series
        Synthetic discount target in [0.0, 0.5].  (M3 regressor)
        Formula: stock_pressure * 0.3 + (1 - shelf_life_hours / 10) * 0.2
    """
    url, key = _load_env()
    rows = _fetch_rows(url, key)

    if not rows:
        raise ValueError("inventory_features table returned 0 rows — run seed_data.py first.")

    df = pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Derive price_history_mean from the JSONB array column
    # ------------------------------------------------------------------
    def _mean_price(val) -> float:
        """Accept list, already-parsed list, or None; return float mean."""
        if val is None:
            return float("nan")
        if isinstance(val, list):
            arr = val
        else:
            import json
            arr = json.loads(val)
        return float(np.mean(arr)) if arr else float("nan")

    df["price_history_mean"] = df["price_history_7d"].apply(_mean_price)

    # ------------------------------------------------------------------
    # Feature matrix X (6 frozen columns, indexed by item_id)
    # ------------------------------------------------------------------
    df = df.set_index("item_id")
    X = df[FEATURE_COLS].astype(float)

    # ------------------------------------------------------------------
    # Label columns
    # ------------------------------------------------------------------
    shelf = df["shelf_life_hours"].astype(float)

    y_expiry = (shelf < 6).astype(int).rename("expiry_label")

    raw_discount = df["stock_pressure"].astype(float) * 0.3 + (1 - shelf / 10) * 0.2
    y_discount = raw_discount.clip(0.0, 0.5).rename("discount_label")

    return X, y_expiry, y_discount


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    X, y_expiry, y_discount = load_features()

    print("=" * 60)
    print(f"Feature matrix shape: {X.shape}")
    print(f"Columns: {list(X.columns)}")
    print()
    print("First 3 rows of X:")
    print(X.head(3).to_string())
    print()
    print("y_expiry distribution:")
    print(y_expiry.value_counts().sort_index().to_string())
    print()
    print("y_discount stats:")
    print(y_discount.describe().to_string())
