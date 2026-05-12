"""
seed_data.py — Seed 12 Belgium Bakery & Deli demo items into Supabase `inventory_features`.

Uses the PostgREST REST API directly (httpx) because supabase-py 2.x validates
keys as JWTs, which rejects Supabase's newer `sb_publishable_*` / `sb_secret_*`
key format introduced in 2025.

Requires SUPABASE_SERVICE_ROLE_KEY in .env for INSERT (RLS bypass).
The anon key only has SELECT rights by default.

Usage:
    cd src/ml
    python seed_data.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Load .env from the same directory as this script
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]

# Prefer service role key (bypasses RLS); fall back to anon key
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]

ITEMS = [
    {
        "item_id": "SKU-002",
        "name_fr": "Poulet rôti Label Rouge 1.2kg",
        "name_nl": "Gebraden kip Label Rouge 1.2kg",
        "current_price": 9.99,
        "stock": 8,
        "shelf_life_hours": 3,
        "sales_velocity_7d": 2.8,
        "inventory_age_days": 2,
        "stock_pressure": 0.72,
        "hour_of_day": 17,
        "weather_signal": 0.3,
    },
    {
        "item_id": "SKU-008",
        "name_fr": "Baguette tradition x2",
        "name_nl": "Traditioneel stokbrood x2",
        "current_price": 1.79,
        "stock": 28,
        "shelf_life_hours": 3,
        "sales_velocity_7d": 9.4,
        "inventory_age_days": 1,
        "stock_pressure": 0.56,
        "hour_of_day": 17,
        "weather_signal": 0.5,
    },
    {
        "item_id": "SKU-005",
        "name_fr": "Pain de campagne 400g",
        "name_nl": "Boerenbrood 400g",
        "current_price": 2.49,
        "stock": 31,
        "shelf_life_hours": 4,
        "sales_velocity_7d": 11.6,
        "inventory_age_days": 1,
        "stock_pressure": 0.62,
        "hour_of_day": 17,
        "weather_signal": 0.5,
    },
    {
        "item_id": "SKU-006",
        "name_fr": "Quiche Lorraine 4 personnes",
        "name_nl": "Quiche Lorraine 4 personen",
        "current_price": 5.49,
        "stock": 11,
        "shelf_life_hours": 4,
        "sales_velocity_7d": 3.1,
        "inventory_age_days": 3,
        "stock_pressure": 0.44,
        "hour_of_day": 17,
        "weather_signal": 0.2,
    },
    {
        "item_id": "SKU-003",
        "name_fr": "Croissants beurre x6",
        "name_nl": "Boterkoeken x6",
        "current_price": 2.89,
        "stock": 24,
        "shelf_life_hours": 5,
        "sales_velocity_7d": 9.1,
        "inventory_age_days": 2,
        "stock_pressure": 0.48,
        "hour_of_day": 17,
        "weather_signal": 0.4,
    },
    {
        "item_id": "SKU-010",
        "name_fr": "Fromage frais aux herbes 200g",
        "name_nl": "Verse kruidenkaas 200g",
        "current_price": 2.29,
        "stock": 16,
        "shelf_life_hours": 5,
        "sales_velocity_7d": 5.2,
        "inventory_age_days": 2,
        "stock_pressure": 0.53,
        "hour_of_day": 17,
        "weather_signal": 0.3,
    },
    {
        "item_id": "SKU-001",
        "name_fr": "Fraises biologiques 500g",
        "name_nl": "Biologische aardbeien 500g",
        "current_price": 3.49,
        "stock": 17,
        "shelf_life_hours": 6,
        "sales_velocity_7d": 4.2,
        "inventory_age_days": 3,
        "stock_pressure": 0.34,
        "hour_of_day": 17,
        "weather_signal": 0.6,
    },
    {
        "item_id": "SKU-007",
        "name_fr": "Tarte aux pommes 6 parts",
        "name_nl": "Appeltaart 6 stukken",
        "current_price": 3.99,
        "stock": 14,
        "shelf_life_hours": 6,
        "sales_velocity_7d": 4.8,
        "inventory_age_days": 2,
        "stock_pressure": 0.56,
        "hour_of_day": 17,
        "weather_signal": 0.4,
    },
    {
        "item_id": "SKU-011",
        "name_fr": "Wrap poulet César 220g",
        "name_nl": "Wrap kip César 220g",
        "current_price": 3.19,
        "stock": 19,
        "shelf_life_hours": 6,
        "sales_velocity_7d": 6.7,
        "inventory_age_days": 1,
        "stock_pressure": 0.38,
        "hour_of_day": 17,
        "weather_signal": 0.5,
    },
    {
        "item_id": "SKU-004",
        "name_fr": "Saumon fumé 200g",
        "name_nl": "Gerookte zalm 200g",
        "current_price": 5.99,
        "stock": 12,
        "shelf_life_hours": 7,
        "sales_velocity_7d": 3.4,
        "inventory_age_days": 4,
        "stock_pressure": 0.48,
        "hour_of_day": 17,
        "weather_signal": 0.3,
    },
    {
        "item_id": "SKU-009",
        "name_fr": "Jambon cuit tranché 150g",
        "name_nl": "Gekookte ham gesneden 150g",
        "current_price": 2.99,
        "stock": 22,
        "shelf_life_hours": 7,
        "sales_velocity_7d": 7.1,
        "inventory_age_days": 2,
        "stock_pressure": 0.44,
        "hour_of_day": 17,
        "weather_signal": 0.4,
    },
    {
        "item_id": "SKU-012",
        "name_fr": "Soupe de légumes 600ml",
        "name_nl": "Groentesoep 600ml",
        "current_price": 2.79,
        "stock": 18,
        "shelf_life_hours": 7,
        "sales_velocity_7d": 5.9,
        "inventory_age_days": 2,
        "stock_pressure": 0.36,
        "hour_of_day": 17,
        "weather_signal": 0.2,
    },
]


def build_rows(items: list[dict]) -> list[dict]:
    """Enrich each item with price_history_7d, expiry_risk, discount_pct."""
    rows = []
    for item in items:
        price = float(item["current_price"])
        row = dict(item)
        row["price_history_7d"] = [price] * 7
        row["expiry_risk"] = None   # filled by M2 model later
        row["discount_pct"] = None  # filled by M3 model later
        rows.append(row)
    return rows


def main() -> None:
    using_service_key = bool(os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    key_label = "service_role" if using_service_key else "anon"
    print(f"Using key type: {key_label}")

    base_url = SUPABASE_URL.rstrip("/")
    endpoint = f"{base_url}/rest/v1/inventory_features"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",  # upsert on conflict
    }

    rows = build_rows(ITEMS)

    print(f"Upserting {len(rows)} rows into inventory_features ...")

    with httpx.Client(timeout=30.0) as client:
        # Upsert all rows in a single request
        response = client.post(endpoint, headers=headers, json=rows)

        if response.status_code == 401 and not using_service_key:
            print()
            print("ERROR: HTTP 401 — RLS blocks anon key from writing.")
            print()
            print("Fix: add SUPABASE_SERVICE_ROLE_KEY to src/ml/.env")
            print("  Get it from: Supabase Dashboard > Project Settings > API > service_role key")
            print("  Then re-run: python seed_data.py")
            print()
            print("Alternative: run this SQL in Supabase Dashboard > SQL Editor:")
            print("  ALTER TABLE inventory_features DISABLE ROW LEVEL SECURITY;")
            print("  (re-enable after seeding if needed)")
            sys.exit(1)

        if response.status_code not in (200, 201, 204):
            print(f"ERROR: upsert failed with HTTP {response.status_code}")
            print(response.text)
            sys.exit(1)

        print(f"Upsert HTTP {response.status_code} — OK")

        # Verify by counting rows back
        verify_headers = {**headers, "Prefer": "count=exact"}
        verify = client.get(
            endpoint,
            headers=verify_headers,
            params={"select": "item_id"},
        )
        if verify.status_code != 200:
            print(f"WARNING: verification query failed with HTTP {verify.status_code}")
        else:
            data = verify.json()
            count = len(data)
            content_range = verify.headers.get("content-range", "")
            print(f"Rows in inventory_features: {count}  (Content-Range: {content_range})")

            if count < len(rows):
                print(f"WARNING: expected {len(rows)} rows, found {count}.")
            else:
                print("All 12 demo items confirmed in database.")


if __name__ == "__main__":
    main()
