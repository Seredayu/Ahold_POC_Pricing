"""
export_model.py — Train M2 + M3 on full dataset and write models/ artefacts.

Run this after reviewing evaluate.py output.

Usage:
    cd src/ml
    python export_model.py
"""

from pathlib import Path

import joblib

from train_m2 import train as train_m2
from train_m3 import train as train_m3

MODELS_DIR = Path(__file__).parent / "models"


if __name__ == "__main__":
    MODELS_DIR.mkdir(exist_ok=True)

    print("Training M2 (expiry risk classifier) ...")
    m2, _, _ = train_m2()
    m2_path = MODELS_DIR / "m2.pkl"
    joblib.dump(m2, m2_path)
    print(f"  saved -> {m2_path}")

    print("Training M3 (discount % regressor) ...")
    m3, _, _ = train_m3(m2_model=m2)
    m3_path = MODELS_DIR / "m3.pkl"
    joblib.dump(m3, m3_path)
    print(f"  saved -> {m3_path}")

    print("\nDone. Run evaluate.py for LOO-CV metrics.")
