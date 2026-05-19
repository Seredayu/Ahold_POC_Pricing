"""
evaluate.py — Cross-validated metrics for M2 (classifier) and M3 (regressor).

With only 12 demo items, uses LeaveOneOut CV for unbiased estimates.

M2 metrics : precision, recall, F1, ROC-AUC
M3 metrics : MAE, RMSE, margin-recovery vs zero-discount baseline

Requires models/m2.pkl (for M3 feature augmentation).

Usage:
    cd src/ml
    python evaluate.py
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneOut
from xgboost import XGBClassifier, XGBRegressor

from feature_pipeline import load_features

MODELS_DIR = Path(__file__).parent / "models"


def _m2_params() -> dict:
    return dict(n_estimators=50, max_depth=3, learning_rate=0.1,
                eval_metric="logloss", random_state=42, verbosity=0)


def _m3_params() -> dict:
    return dict(n_estimators=50, max_depth=3, learning_rate=0.1,
                random_state=42, verbosity=0)


def evaluate_m2(X: pd.DataFrame, y: pd.Series) -> None:
    loo = LeaveOneOut()
    y_true_all, y_pred_all, y_proba_all = [], [], []

    for train_idx, test_idx in loo.split(X):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
        model = XGBClassifier(**_m2_params())
        model.fit(X_tr, y_tr)
        y_true_all.extend(y_te.tolist())
        y_pred_all.extend(model.predict(X_te).tolist())
        y_proba_all.extend(model.predict_proba(X_te)[:, 1].tolist())

    y_true = np.array(y_true_all)
    y_pred = np.array(y_pred_all)
    y_proba = np.array(y_proba_all)

    print("=== M2 Expiry Risk Classifier — LOO-CV ===")
    print(f"  Precision : {precision_score(y_true, y_pred, zero_division=0):.3f}")
    print(f"  Recall    : {recall_score(y_true, y_pred, zero_division=0):.3f}")
    print(f"  F1        : {f1_score(y_true, y_pred, zero_division=0):.3f}")
    if len(np.unique(y_true)) > 1:
        print(f"  ROC-AUC   : {roc_auc_score(y_true, y_proba):.3f}")
    else:
        print("  ROC-AUC   : N/A (single class in LOO splits)")
    print(f"  Label dist: {np.bincount(y_true.astype(int))}")


def evaluate_m3(X: pd.DataFrame, y: pd.Series, m2_model) -> None:
    loo = LeaveOneOut()
    y_true_all, y_pred_all = [], []

    for train_idx, test_idx in loo.split(X):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]

        # Fit a fresh M2 on the training fold for feature augmentation
        m2_fold = XGBClassifier(**_m2_params())
        m2_fold.fit(X_tr, (m2_model.predict_proba(X_tr)[:, 1] >= 0.5).astype(int))

        X_tr_m3 = X_tr.copy()
        X_tr_m3["expiry_risk"] = m2_fold.predict_proba(X_tr)[:, 1]
        X_te_m3 = X_te.copy()
        X_te_m3["expiry_risk"] = m2_fold.predict_proba(X_te)[:, 1]

        model = XGBRegressor(**_m3_params())
        model.fit(X_tr_m3, y_tr)
        y_true_all.extend(y_te.tolist())
        y_pred_all.extend(np.clip(model.predict(X_te_m3), 0.0, 0.5).tolist())

    y_true = np.array(y_true_all)
    y_pred = np.array(y_pred_all)

    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    # Margin recovery: 1 − MAE / baseline MAE (baseline = always predict 0 discount)
    baseline_mae = mean_absolute_error(y_true, np.zeros_like(y_true))
    margin_recovery = 1.0 - mae / baseline_mae if baseline_mae > 0 else 0.0

    print("\n=== M3 Discount % Regressor — LOO-CV ===")
    print(f"  MAE             : {mae:.4f}")
    print(f"  RMSE            : {rmse:.4f}")
    print(f"  Margin recovery : {margin_recovery:.3f}  (vs zero-discount baseline)")
    print(f"  Target range    : [{y_true.min():.3f}, {y_true.max():.3f}]")
    print(f"  Pred range      : [{y_pred.min():.3f}, {y_pred.max():.3f}]")


if __name__ == "__main__":
    m2_path = MODELS_DIR / "m2.pkl"
    if not m2_path.exists():
        raise SystemExit(f"Run train_m2.py first — {m2_path} not found.")

    m2 = joblib.load(m2_path)
    X, y_expiry, y_discount = load_features()

    evaluate_m2(X, y_expiry)
    evaluate_m3(X, y_discount, m2)
