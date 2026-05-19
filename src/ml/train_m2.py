"""
train_m2.py — Train M2 XGBoost binary classifier: expiry_risk_score.

Input:  inventory_features from Supabase (via feature_pipeline.load_features)
Output: models/m2.pkl  — XGBClassifier, predict_proba[:,1] = expiry_risk

Label: 1 if shelf_life_hours < 6, else 0  (72h horizon proxy on 12-item demo set)

Usage:
    cd src/ml
    python train_m2.py
"""

from pathlib import Path

import joblib
import numpy as np
from xgboost import XGBClassifier

from feature_pipeline import load_features, FEATURE_COLS

MODELS_DIR = Path(__file__).parent / "models"


def train(m2_model: XGBClassifier | None = None) -> tuple[XGBClassifier, object, object]:
    """Load features, fit M2, return (model, X, y_expiry)."""
    X, y_expiry, _ = load_features()

    model = m2_model or XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
        verbosity=0,
    )
    model.fit(X, y_expiry)
    return model, X, y_expiry


if __name__ == "__main__":
    MODELS_DIR.mkdir(exist_ok=True)

    model, X, y = train()

    out_path = MODELS_DIR / "m2.pkl"
    joblib.dump(model, out_path)

    proba = model.predict_proba(X)[:, 1]
    preds = (proba >= 0.5).astype(int)

    print(f"M2 saved -> {out_path}")
    print(f"Training accuracy : {(preds == y.values).mean():.3f}")
    print(f"Label distribution: {np.bincount(y.values)}")
    print(f"Expiry risk range : [{proba.min():.3f}, {proba.max():.3f}]")
