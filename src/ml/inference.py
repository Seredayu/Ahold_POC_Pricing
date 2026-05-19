"""
inference.py — FastAPI Phase 2A inference server.

Replaces the Node.js mock BFF:
  GET  /health       liveness check
  GET  /api/items    Supabase + M2/M3 -> enriched item list (sorted by urgency)
  POST /api/approve  ZMKD write-back (idempotent, mocks SAP A004)
  POST /api/reject   rejection log

Run:
    cd src/ml
    uvicorn inference:app --port 8000 --reload
"""

import json
import random
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from feature_pipeline import FEATURE_COLS, _fetch_rows, _load_env

MODELS_DIR = Path(__file__).parent / "models"

_m2 = None
_m3 = None
_approved: set[str] = set()


# ---------------------------------------------------------------------------
# Startup — load or train models
# ---------------------------------------------------------------------------

def _load_or_train() -> None:
    global _m2, _m3
    m2_path = MODELS_DIR / "m2.pkl"
    m3_path = MODELS_DIR / "m3.pkl"

    if not m2_path.exists() or not m3_path.exists():
        print("Models not found — training on full dataset ...")
        MODELS_DIR.mkdir(exist_ok=True)
        from train_m2 import train as _train_m2
        from train_m3 import train as _train_m3

        m2, _, _ = _train_m2()
        joblib.dump(m2, m2_path)
        m3, _, _ = _train_m3(m2_model=m2)
        joblib.dump(m3, m3_path)
        print(f"  M2 saved -> {m2_path}")
        print(f"  M3 saved -> {m3_path}")

    _m2 = joblib.load(m2_path)
    _m3 = joblib.load(m3_path)
    print("Models loaded.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_or_train()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Ahold Markdown POC — Phase 2A Inference", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ApproveRequest(BaseModel):
    item_id: str
    discount_pct: float
    manager_override: bool = False


class RejectRequest(BaseModel):
    item_id: str
    reason_code: str = "associate_judgement"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(offset_days: int = 0) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


def _condition_record() -> str:
    return str(random.randint(1_000_000_000, 9_999_999_999))


def _mean_price(val) -> float:
    if val is None:
        return float("nan")
    arr = val if isinstance(val, list) else json.loads(val)
    return float(np.mean(arr)) if arr else float("nan")


def _run_inference() -> list[dict]:
    """Fetch Supabase features, run M2+M3, return enriched item list."""
    url, key = _load_env()
    rows = _fetch_rows(url, key)
    if not rows:
        return []

    df = pd.DataFrame(rows).set_index("item_id")
    df["price_history_mean"] = df["price_history_7d"].apply(_mean_price)
    X = df[FEATURE_COLS].astype(float)

    expiry_risk = _m2.predict_proba(X)[:, 1]
    X_m3 = X.copy()
    X_m3["expiry_risk"] = expiry_risk
    discount_pct = np.clip(_m3.predict(X_m3), 0.0, 0.5)

    df["_risk"] = expiry_risk
    df["_disc"] = discount_pct

    result = []
    for item_id, row in df.iterrows():
        risk = float(row["_risk"])
        disc = float(row["_disc"])

        if disc < 0.05:
            continue

        price = float(row["current_price"])
        result.append({
            "item": {
                "item_id": item_id,
                "name_fr": str(row.get("name_fr", "")),
                "name_nl": str(row.get("name_nl", "")),
                "current_price": price,
                "stock": int(row["stock"]),
                "hours_to_close": float(row["shelf_life_hours"]),
                "sales_velocity_7d": float(row["sales_velocity_7d"]),
            },
            "rec": {
                "recommended": True,
                "discount_pct": round(disc, 4),
                "recommended_price": round(price * (1 - disc), 2),
                "confidence": round(min(0.60 + risk * 0.39, 0.99), 2),
                "expiry_risk": round(risk, 2),
                "manager_required": disc > 0.5,
                "sales_velocity_7d": float(row["sales_velocity_7d"]),
            },
        })

    result.sort(key=lambda x: x["item"]["hours_to_close"])
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/items")
def get_items():
    return _run_inference()


@app.post("/api/approve")
def approve(body: ApproveRequest):
    if not body.item_id:
        raise HTTPException(status_code=400, detail="item_id required")
    if body.discount_pct > 0.5 and not body.manager_override:
        raise HTTPException(
            status_code=403,
            detail={"error": "manager_approval_required", "discount_pct": body.discount_pct},
        )
    if body.item_id in _approved:
        return {"status": "already_applied", "condition_record": None}

    _approved.add(body.item_id)
    return {
        "status": "zmkd_queued",
        "condition_record": _condition_record(),
        "condition_type": "ZMKD",
        "table": "A004",
        "discount_pct": body.discount_pct,
        "valid_from": _iso(0),
        "valid_to": _iso(1),
    }


@app.post("/api/reject")
def reject(body: RejectRequest):
    if not body.item_id:
        raise HTTPException(status_code=400, detail="item_id required")
    return {"status": "rejected", "item_id": body.item_id, "reason_code": body.reason_code}
