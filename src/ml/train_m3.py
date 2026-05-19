"""
train_m3.py — Train M3 XGBoost regressor: discount_pct output.

Input:  6 frozen features + M2 expiry_risk_score (7th feature)
Output: models/m3.pkl  — XGBRegressor, predict() = discount_pct in [0.0, 0.5]

Requires models/m2.pkl to exist — run train_m2.py first.

Usage:
    cd src/ml
    python train_m3.py
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from feature_pipeline import load_features

MODELS_DIR = Path(__file__).parent / "models"


def _add_expiry_risk(X: pd.DataFrame, m2_model) -> pd.DataFrame:
    """Append M2 expiry_risk_score as a 7th feature column."""
    risk = m2_model.predict_proba(X)[:, 1]
    X_m3 = X.copy()
    X_m3["expiry_risk"] = risk
    return X_m3


def train(m2_model=None) -> tuple[XGBRegressor, pd.DataFrame, pd.Series]:
    """Load features + M2 output, fit M3, return (model, X_m3, y_discount)."""
    if m2_model is None:
        m2_path = MODELS_DIR / "m2.pkl"
        if not m2_path.exists():
            raise FileNotFoundError(f"M2 model not found at {m2_path}. Run train_m2.py first.")
        m2_model = joblib.load(m2_path)

    X, _, y_discount = load_features()
    X_m3 = _add_expiry_risk(X, m2_model)

    model = XGBRegressor(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_m3, y_discount)
    return model, X_m3, y_discount


if __name__ == "__main__":
    MODELS_DIR.mkdir(exist_ok=True)

    model, X_m3, y = train()

    out_path = MODELS_DIR / "m3.pkl"
    joblib.dump(model, out_path)

    preds = np.clip(model.predict(X_m3), 0.0, 0.5)
    mae = float(np.abs(preds - y.values).mean())

    print(f"M3 saved -> {out_path}")
    print(f"Training MAE     : {mae:.4f}")
    print(f"Predicted range  : [{preds.min():.3f}, {preds.max():.3f}]")
    print(f"Target range     : [{y.min():.3f}, {y.max():.3f}]")
