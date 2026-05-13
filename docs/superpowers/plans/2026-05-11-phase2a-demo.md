# Phase 2A Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded decision table with real XGBoost M2+M3 inference, expand to 12 Belgium items in Supabase, and surface expiry risk bar + SHAP-driven XAI reason on the card.

**Architecture:** Supabase holds 12 Belgium demo items with feature values. FastAPI on Railway loads XGBoost pickles and serves `/infer`. Node BFF gains `GET /api/items` that queries Supabase then calls `/infer` per item; existing `/api/approve` and `/api/reject` are unchanged. React card gains an expiry risk bar and SHAP-based reason text.

**Tech Stack:** Python 3.11, xgboost 2.x, scikit-learn, shap, supabase-py, fastapi, uvicorn, httpx (tests); Node 20, @supabase/supabase-js; React + Tailwind (existing).

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/ml/requirements.txt` | Python deps for ML + seeding |
| Create | `src/ml/seed_data.py` | Seed 12 Belgium items into Supabase |
| Create | `src/ml/feature_pipeline.py` | Supabase → flat feature vector |
| Create | `src/ml/train_m2.py` | XGBoost classifier → expiry_risk |
| Create | `src/ml/train_m3.py` | XGBoost regressor → discount_pct |
| Create | `src/ml/export_model.py` | joblib pickle + SHAP explainer |
| Create | `models/.gitkeep` | Ensure models/ dir tracked |
| Create | `src/api/infer.py` | FastAPI inference app |
| Create | `src/api/requirements-api.txt` | FastAPI deps |
| Create | `src/api/railway.toml` | Railway build + start config |
| Create | `tests/test_infer.py` | FastAPI contract tests |
| Create | `.env.example` | Credential template |
| Modify | `src/api/server.js` | Add GET /api/items + Supabase + /infer calls |
| Modify | `src/app/src/App.jsx` | Replace buildQueue(MOCK_ITEMS) with GET /api/items |
| Modify | `src/app/src/lib/i18n.js` | Add expiryRiskLabel; reason now from API |
| Modify | `src/app/src/components/RecommendationCard.jsx` | Add expiry risk bar |
| Modify | `src/app/src/components/DetailView.jsx` | Use reason from rec instead of local template |

---

## Task 1: Python environment + Supabase schema

**Files:**
- Create: `src/ml/requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Create `src/ml/requirements.txt`**

```
xgboost==2.1.3
scikit-learn==1.5.2
shap==0.46.0
supabase==2.10.0
pandas==2.2.3
numpy==1.26.4
joblib==1.4.2
```

- [ ] **Step 2: Install deps**

```bash
cd src/ml && python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Create Supabase project**

Go to https://supabase.com → New project → name `ahold-poc-pricing` → region `eu-west-1` (Belgium closest) → copy Project URL and anon key.

- [ ] **Step 4: Run schema SQL in Supabase SQL Editor**

```sql
CREATE TABLE inventory_features (
  item_id            TEXT PRIMARY KEY,
  name_fr            TEXT NOT NULL,
  name_nl            TEXT NOT NULL,
  current_price      NUMERIC(10,2) NOT NULL,
  stock              INTEGER NOT NULL,
  shelf_life_hours   INTEGER NOT NULL,
  sales_velocity_7d  NUMERIC(10,4) NOT NULL,
  inventory_age_days INTEGER NOT NULL,
  stock_pressure     NUMERIC(5,4) NOT NULL,
  hour_of_day        INTEGER NOT NULL,
  weather_signal     NUMERIC(5,2) NOT NULL,
  price_history_7d   JSONB NOT NULL,
  expiry_risk        NUMERIC(5,4),
  discount_pct       NUMERIC(5,4)
);
```

Expected: table created, no errors.

- [ ] **Step 5: Create `.env.example`**

```
# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...

# FastAPI (Railway)
INFER_API_KEY=change-me-32-chars-minimum
RAILWAY_URL=https://your-app.up.railway.app

# Set in src/ml/.env and src/api/.env — never commit real values
```

- [ ] **Step 6: Create `src/ml/.env` and `src/api/.env`** (not committed)

Copy `.env.example` to both paths, fill in real Supabase credentials and a generated API key (`python -c "import secrets; print(secrets.token_hex(32))"`).

Verify `.gitignore` contains `*.env` and `.env`.

- [ ] **Step 7: Commit**

```bash
git add src/ml/requirements.txt .env.example
git commit -m "feat(phase2a): python env + supabase schema"
```

---

## Task 2: Seed 12 Belgium items into Supabase

**Files:**
- Create: `src/ml/seed_data.py`

- [ ] **Step 1: Create `src/ml/seed_data.py`**

```python
"""Seed 12 Belgium Bakery & Deli items into Supabase inventory_features."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

ITEMS = [
    {"item_id":"SKU-002","name_fr":"Poulet rôti Label Rouge 1.2kg","name_nl":"Geroosterde kip Label Rouge 1.2kg","current_price":9.99,"stock":8,"shelf_life_hours":3,"sales_velocity_7d":2.8,"inventory_age_days":2,"stock_pressure":0.27,"hour_of_day":17,"weather_signal":0.3,"price_history_7d":[9.99,9.99,9.99,9.99,10.49,10.49,9.99]},
    {"item_id":"SKU-008","name_fr":"Baguette tradition x2","name_nl":"Traditioneel stokbrood x2","current_price":1.79,"stock":28,"shelf_life_hours":3,"sales_velocity_7d":9.4,"inventory_age_days":1,"stock_pressure":0.93,"hour_of_day":17,"weather_signal":0.5,"price_history_7d":[1.79,1.79,1.79,1.79,1.79,1.79,1.79]},
    {"item_id":"SKU-005","name_fr":"Pain de campagne 400g","name_nl":"Boerenbrood 400g","current_price":2.49,"stock":31,"shelf_life_hours":4,"sales_velocity_7d":11.6,"inventory_age_days":1,"stock_pressure":1.0,"hour_of_day":17,"weather_signal":0.5,"price_history_7d":[2.49,2.49,2.49,2.49,2.49,2.49,2.49]},
    {"item_id":"SKU-006","name_fr":"Quiche Lorraine 4 personnes","name_nl":"Quiche Lorraine 4 personen","current_price":5.49,"stock":11,"shelf_life_hours":4,"sales_velocity_7d":3.1,"inventory_age_days":2,"stock_pressure":0.37,"hour_of_day":17,"weather_signal":0.2,"price_history_7d":[5.49,5.49,5.99,5.99,5.49,5.49,5.49]},
    {"item_id":"SKU-003","name_fr":"Croissants beurre x6","name_nl":"Boter croissants x6","current_price":2.89,"stock":24,"shelf_life_hours":5,"sales_velocity_7d":9.1,"inventory_age_days":1,"stock_pressure":0.80,"hour_of_day":17,"weather_signal":0.4,"price_history_7d":[2.89,2.89,2.89,2.89,2.89,2.89,2.89]},
    {"item_id":"SKU-010","name_fr":"Fromage frais aux herbes 200g","name_nl":"Verse kruidenkaas 200g","current_price":2.29,"stock":16,"shelf_life_hours":5,"sales_velocity_7d":5.2,"inventory_age_days":3,"stock_pressure":0.53,"hour_of_day":17,"weather_signal":0.3,"price_history_7d":[2.29,2.29,2.29,2.29,2.49,2.49,2.29]},
    {"item_id":"SKU-001","name_fr":"Fraises biologiques 500g","name_nl":"Biologische aardbeien 500g","current_price":3.49,"stock":17,"shelf_life_hours":6,"sales_velocity_7d":4.2,"inventory_age_days":2,"stock_pressure":0.57,"hour_of_day":17,"weather_signal":0.6,"price_history_7d":[3.49,3.49,3.49,3.49,3.49,3.49,3.49]},
    {"item_id":"SKU-007","name_fr":"Tarte aux pommes 6 parts","name_nl":"Appeltaart 6 stukken","current_price":3.99,"stock":14,"shelf_life_hours":6,"sales_velocity_7d":4.8,"inventory_age_days":2,"stock_pressure":0.47,"hour_of_day":17,"weather_signal":0.4,"price_history_7d":[3.99,3.99,3.99,4.29,4.29,3.99,3.99]},
    {"item_id":"SKU-011","name_fr":"Wrap poulet César 220g","name_nl":"Kip César wrap 220g","current_price":3.19,"stock":19,"shelf_life_hours":6,"sales_velocity_7d":6.7,"inventory_age_days":1,"stock_pressure":0.63,"hour_of_day":17,"weather_signal":0.5,"price_history_7d":[3.19,3.19,3.19,3.19,3.19,3.19,3.19]},
    {"item_id":"SKU-004","name_fr":"Saumon fumé 200g","name_nl":"Gerookte zalm 200g","current_price":5.99,"stock":12,"shelf_life_hours":7,"sales_velocity_7d":3.4,"inventory_age_days":3,"stock_pressure":0.40,"hour_of_day":17,"weather_signal":0.3,"price_history_7d":[5.99,5.99,5.99,5.99,6.49,6.49,5.99]},
    {"item_id":"SKU-009","name_fr":"Jambon cuit tranché 150g","name_nl":"Gekookte ham gesneden 150g","current_price":2.99,"stock":22,"shelf_life_hours":7,"sales_velocity_7d":7.1,"inventory_age_days":2,"stock_pressure":0.73,"hour_of_day":17,"weather_signal":0.4,"price_history_7d":[2.99,2.99,2.99,2.99,2.99,2.99,2.99]},
    {"item_id":"SKU-012","name_fr":"Soupe de légumes 600ml","name_nl":"Groentesoep 600ml","current_price":2.79,"stock":18,"shelf_life_hours":7,"sales_velocity_7d":5.9,"inventory_age_days":2,"stock_pressure":0.60,"hour_of_day":17,"weather_signal":0.2,"price_history_7d":[2.79,2.79,2.79,2.79,2.79,2.79,2.79]},
]

def main():
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    result = client.table("inventory_features").upsert(ITEMS).execute()
    print(f"Seeded {len(result.data)} items")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add python-dotenv to requirements**

Append to `src/ml/requirements.txt`:
```
python-dotenv==1.0.1
```

Then `pip install python-dotenv`.

- [ ] **Step 3: Run seed**

```bash
cd src/ml && python seed_data.py
```

Expected output: `Seeded 12 items`

Verify in Supabase Table Editor: 12 rows in `inventory_features`.

- [ ] **Step 4: Commit**

```bash
git add src/ml/seed_data.py src/ml/requirements.txt
git commit -m "feat(phase2a): seed 12 Belgium items to Supabase"
```

---

## Task 3: Feature pipeline

**Files:**
- Create: `src/ml/feature_pipeline.py`

- [ ] **Step 1: Create `src/ml/feature_pipeline.py`**

```python
"""Query Supabase → flat feature vectors for M2/M3 training and inference."""
import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

FEATURE_COLS = [
    'inventory_age_days',
    'stock_pressure',
    'hour_of_day',
    'sales_velocity_7d',
    'weather_signal',
    'price_history_7d',   # scalar: mean of 7-day list
]

def fetch_features(client=None) -> pd.DataFrame:
    """Return DataFrame with FEATURE_COLS columns, indexed by item_id."""
    if client is None:
        client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    rows = client.table("inventory_features").select("*").execute().data
    df = pd.DataFrame(rows).set_index("item_id")
    # Flatten price_history_7d list → mean scalar
    df['price_history_7d'] = df['price_history_7d'].apply(
        lambda x: float(np.mean(x)) if isinstance(x, list) else float(x)
    )
    return df

def to_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Return X matrix with exactly FEATURE_COLS columns in order."""
    return df[FEATURE_COLS].astype(float)

if __name__ == "__main__":
    df = fetch_features()
    X = to_feature_matrix(df)
    print(X.to_string())
```

- [ ] **Step 2: Run pipeline to verify**

```bash
cd src/ml && python feature_pipeline.py
```

Expected: 12 rows printed with 6 float columns.

- [ ] **Step 3: Commit**

```bash
git add src/ml/feature_pipeline.py
git commit -m "feat(phase2a): feature pipeline — Supabase → 6-col feature matrix"
```

---

## Task 4: Generate synthetic training data + train M2

**Files:**
- Create: `src/ml/train_m2.py`
- Create: `models/.gitkeep`

- [ ] **Step 1: Create `models/` directory**

```bash
mkdir -p models && touch models/.gitkeep
```

- [ ] **Step 2: Create `src/ml/train_m2.py`**

```python
"""Train M2: XGBoost binary classifier → expiry_risk score (0–1).
Label: shelf_life_hours < 6  (1 = will expire soon, recommend markdown)
"""
import os
import numpy as np
import pandas as pd
import joblib
from dotenv import load_dotenv
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from feature_pipeline import FEATURE_COLS

load_dotenv()

def generate_training_data(n: int = 8000, seed: int = 42) -> pd.DataFrame:
    """Synthetic dataset with same feature schema as production items."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        'inventory_age_days': rng.integers(0, 10, n),
        'stock_pressure':     rng.uniform(0.1, 1.0, n),
        'hour_of_day':        rng.integers(8, 22, n),
        'sales_velocity_7d':  rng.exponential(5.0, n).clip(0.5, 20),
        'weather_signal':     rng.uniform(0.0, 1.0, n),
        'price_history_7d':   rng.uniform(1.0, 15.0, n),  # mean of 7-day series
        'shelf_life_hours':   rng.integers(1, 12, n),
    })
    # Items with shelf_life_hours < 6 AND stock_pressure > 0.3 are high-risk
    df['label'] = ((df['shelf_life_hours'] < 6) & (df['stock_pressure'] > 0.3)).astype(int)
    return df

def main():
    df = generate_training_data()
    X = df[FEATURE_COLS]
    y = df['label']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    print(f"M2 ROC-AUC: {auc:.4f}")  # expect > 0.85

    os.makedirs("../../models", exist_ok=True)
    joblib.dump(model, "../../models/m2.pkl")
    print("Saved ../../models/m2.pkl")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run M2 training**

```bash
cd src/ml && python train_m2.py
```

Expected output:
```
M2 ROC-AUC: 0.9xxx
Saved ../../models/m2.pkl
```

AUC below 0.80 means the label definition or feature range is wrong — check `generate_training_data`.

- [ ] **Step 4: Commit**

```bash
git add src/ml/train_m2.py models/.gitkeep
git commit -m "feat(phase2a): train M2 expiry-risk classifier (XGBoost)"
```

---

## Task 5: Train M3 + export SHAP

**Files:**
- Create: `src/ml/train_m3.py`
- Create: `src/ml/export_model.py`

- [ ] **Step 1: Create `src/ml/train_m3.py`**

```python
"""Train M3: XGBoost regressor → discount_pct (0.05–0.50).
Target: synthetic discount driven by shelf_life urgency + stock pressure.
"""
import os
import numpy as np
import pandas as pd
import joblib
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from feature_pipeline import FEATURE_COLS
from train_m2 import generate_training_data

def add_discount_target(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    urgency = 1 - df['shelf_life_hours'] / 12          # 0→low urgency, ~1→high
    pressure = df['stock_pressure']
    noise = rng.normal(0, 0.015, len(df))
    df['discount_pct'] = (0.08 + 0.32 * urgency + 0.10 * pressure + noise).clip(0.05, 0.50)
    return df

def main():
    df = generate_training_data()
    df = add_discount_target(df)
    X = df[FEATURE_COLS]
    y = df['discount_pct']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    mae = mean_absolute_error(y_test, model.predict(X_test))
    print(f"M3 MAE: {mae:.4f}")  # expect < 0.02

    os.makedirs("../../models", exist_ok=True)
    joblib.dump(model, "../../models/m3.pkl")
    print("Saved ../../models/m3.pkl")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run M3 training**

```bash
cd src/ml && python train_m3.py
```

Expected:
```
M3 MAE: 0.0xxx
Saved ../../models/m3.pkl
```

MAE above 0.05 is a red flag — check `add_discount_target`.

- [ ] **Step 3: Create `src/ml/export_model.py`**

```python
"""Export SHAP explainer for M3 → models/shap_m3.pkl.
Also validates M2 + M3 load correctly and produce expected output shapes.
"""
import joblib
import shap
import numpy as np
import pandas as pd
from feature_pipeline import FEATURE_COLS

SHAP_TEMPLATES = {
    'stock_pressure':    ('stock élevé',          'hoge voorraad'),
    'hour_of_day':       ('fin de journée',        'einde dag'),
    'sales_velocity_7d': ('ventes en baisse',      'dalende verkoop'),
    'weather_signal':    ('météo défavorable',     'slecht weer'),
    'inventory_age_days':('stock ancien',          'oud voorraad'),
    'price_history_7d':  ('historique prix stable','stabiele prijshistorie'),
}

def shap_reason(shap_values: np.ndarray, top_n: int = 3) -> tuple[str, str]:
    """Return (reason_fr, reason_nl) from SHAP importance array."""
    top_idx = np.argsort(np.abs(shap_values))[::-1][:top_n]
    top_features = [FEATURE_COLS[i] for i in top_idx]
    fr_tokens = [SHAP_TEMPLATES[f][0] for f in top_features if f in SHAP_TEMPLATES]
    nl_tokens = [SHAP_TEMPLATES[f][1] for f in top_features if f in SHAP_TEMPLATES]
    return ' · '.join(fr_tokens), ' · '.join(nl_tokens)

def main():
    m2 = joblib.load("../../models/m2.pkl")
    m3 = joblib.load("../../models/m3.pkl")

    # Validate shapes on a dummy row
    dummy = pd.DataFrame([{f: 0.5 for f in FEATURE_COLS}])
    risk = float(m2.predict_proba(dummy)[0, 1])
    disc = float(m3.predict(dummy)[0])
    assert 0 <= risk <= 1, f"M2 output out of range: {risk}"
    assert 0 <= disc <= 0.5, f"M3 output out of range: {disc}"
    print(f"Validation — expiry_risk: {risk:.4f}, discount_pct: {disc:.4f}")

    # Build SHAP explainer for M3
    explainer = shap.TreeExplainer(m3)
    joblib.dump({'explainer': explainer, 'templates': SHAP_TEMPLATES}, "../../models/shap_m3.pkl")
    print("Saved ../../models/shap_m3.pkl")

    # Smoke-test reason generation
    shap_vals = explainer.shap_values(dummy)[0]
    reason_fr, reason_nl = shap_reason(shap_vals)
    print(f"reason_fr: {reason_fr}")
    print(f"reason_nl: {reason_nl}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run export**

```bash
cd src/ml && python export_model.py
```

Expected:
```
Validation — expiry_risk: 0.xxxx, discount_pct: 0.xxxx
Saved ../../models/shap_m3.pkl
reason_fr: <3 French tokens joined by ·>
reason_nl: <3 Dutch tokens joined by ·>
```

- [ ] **Step 5: Add models to git (pkl files are small — < 5MB total)**

```bash
git add models/m2.pkl models/m3.pkl models/shap_m3.pkl src/ml/train_m3.py src/ml/export_model.py
git commit -m "feat(phase2a): train M3 discount regressor + SHAP export"
```

---

## Task 6: FastAPI inference API

**Files:**
- Create: `src/api/infer.py`
- Create: `src/api/requirements-api.txt`
- Create: `src/api/railway.toml`
- Create: `tests/test_infer.py`

- [ ] **Step 1: Create `src/api/requirements-api.txt`**

```
fastapi==0.115.5
uvicorn==0.32.1
xgboost==2.1.3
scikit-learn==1.5.2
shap==0.46.0
joblib==1.4.2
pandas==2.2.3
numpy==1.26.4
httpx==0.27.2
pytest==8.3.3
python-dotenv==1.0.1
```

- [ ] **Step 2: Create `src/api/infer.py`**

```python
"""FastAPI inference endpoint — serves M2 expiry_risk + M3 discount_pct."""
import os
from contextlib import asynccontextmanager
from typing import Annotated
import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

FEATURE_COLS = [
    'inventory_age_days', 'stock_pressure', 'hour_of_day',
    'sales_velocity_7d', 'weather_signal', 'price_history_7d',
]

MODELS: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
    MODELS['m2'] = joblib.load(os.path.join(base, 'm2.pkl'))
    MODELS['m3'] = joblib.load(os.path.join(base, 'm3.pkl'))
    shap_data = joblib.load(os.path.join(base, 'shap_m3.pkl'))
    MODELS['shap_explainer'] = shap_data['explainer']
    MODELS['shap_templates'] = shap_data['templates']
    yield

app = FastAPI(lifespan=lifespan)

API_KEY = os.environ.get("INFER_API_KEY", "")

def verify_key(x_api_key: Annotated[str | None, Header()] = None):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

class InferRequest(BaseModel):
    item_id: str
    inventory_age_days: float
    stock_pressure: float
    hour_of_day: float
    sales_velocity_7d: float
    weather_signal: float
    price_history_7d: list[float]  # 7 values → mean used as feature

class InferResponse(BaseModel):
    expiry_risk: float
    discount_pct: float
    confidence: float
    reason_fr: str
    reason_nl: str

def _shap_reason(shap_values: np.ndarray, templates: dict, top_n: int = 3) -> tuple[str, str]:
    top_idx = np.argsort(np.abs(shap_values))[::-1][:top_n]
    top_features = [FEATURE_COLS[i] for i in top_idx]
    fr = [templates[f][0] for f in top_features if f in templates]
    nl = [templates[f][1] for f in top_features if f in templates]
    return ' · '.join(fr), ' · '.join(nl)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/infer", response_model=InferResponse)
def infer(req: InferRequest, x_api_key: Annotated[str | None, Header()] = None):
    verify_key(x_api_key)

    price_mean = float(np.mean(req.price_history_7d)) if req.price_history_7d else req.stock_pressure
    X = pd.DataFrame([{
        'inventory_age_days': req.inventory_age_days,
        'stock_pressure':     req.stock_pressure,
        'hour_of_day':        req.hour_of_day,
        'sales_velocity_7d':  req.sales_velocity_7d,
        'weather_signal':     req.weather_signal,
        'price_history_7d':   price_mean,
    }])

    expiry_risk = float(MODELS['m2'].predict_proba(X)[0, 1])
    discount_pct = float(np.clip(MODELS['m3'].predict(X)[0], 0.05, 0.50))
    confidence = float(MODELS['m2'].predict_proba(X)[0].max())

    shap_vals = MODELS['shap_explainer'].shap_values(X)[0]
    reason_fr, reason_nl = _shap_reason(shap_vals, MODELS['shap_templates'])

    return InferResponse(
        expiry_risk=round(expiry_risk, 4),
        discount_pct=round(discount_pct, 4),
        confidence=round(confidence, 4),
        reason_fr=reason_fr,
        reason_nl=reason_nl,
    )
```

- [ ] **Step 3: Create `src/api/railway.toml`**

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn infer:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
```

- [ ] **Step 4: Write failing tests — `tests/test_infer.py`**

```bash
mkdir -p tests && touch tests/__init__.py
```

```python
"""Contract tests for FastAPI /infer endpoint."""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'api'))

# Patch env before import
os.environ.setdefault("INFER_API_KEY", "test-key-abc123")

from infer import app  # noqa: E402

client = TestClient(app)

VALID_PAYLOAD = {
    "item_id": "SKU-002",
    "inventory_age_days": 2,
    "stock_pressure": 0.72,
    "hour_of_day": 17,
    "sales_velocity_7d": 2.8,
    "weather_signal": 0.3,
    "price_history_7d": [9.99, 9.99, 9.99, 9.99, 10.49, 10.49, 9.99],
}

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_infer_returns_401_without_key():
    r = client.post("/infer", json=VALID_PAYLOAD)
    assert r.status_code == 401

def test_infer_returns_200_with_valid_key():
    r = client.post("/infer", json=VALID_PAYLOAD, headers={"x-api-key": "test-key-abc123"})
    assert r.status_code == 200

def test_infer_response_shape():
    r = client.post("/infer", json=VALID_PAYLOAD, headers={"x-api-key": "test-key-abc123"})
    body = r.json()
    assert set(body.keys()) == {"expiry_risk", "discount_pct", "confidence", "reason_fr", "reason_nl"}

def test_infer_value_ranges():
    r = client.post("/infer", json=VALID_PAYLOAD, headers={"x-api-key": "test-key-abc123"})
    body = r.json()
    assert 0 <= body["expiry_risk"] <= 1
    assert 0.05 <= body["discount_pct"] <= 0.50
    assert 0 <= body["confidence"] <= 1

def test_infer_reason_is_bilingual():
    r = client.post("/infer", json=VALID_PAYLOAD, headers={"x-api-key": "test-key-abc123"})
    body = r.json()
    assert len(body["reason_fr"]) > 0
    assert len(body["reason_nl"]) > 0
    assert " · " in body["reason_fr"]
```

- [ ] **Step 5: Run tests — expect failures (models not on path yet)**

```bash
cd src/api && pip install -r requirements-api.txt
cd ../.. && pytest tests/test_infer.py -v 2>&1 | head -30
```

Expected: tests fail with import or model-load error (confirms tests run).

- [ ] **Step 6: Fix model path and run tests again**

The `lifespan` function uses `../../models` relative to `src/api/infer.py`. When running pytest from repo root, this resolves correctly. If it fails, set env var:

```bash
MODEL_DIR=models pytest tests/test_infer.py -v
```

Update `infer.py` lifespan to use `MODEL_DIR` env var if set:
```python
base = os.environ.get("MODEL_DIR") or os.path.join(os.path.dirname(__file__), '..', '..', 'models')
```

- [ ] **Step 7: Run tests — all must pass**

```bash
pytest tests/test_infer.py -v
```

Expected:
```
tests/test_infer.py::test_health PASSED
tests/test_infer.py::test_infer_returns_401_without_key PASSED
tests/test_infer.py::test_infer_returns_200_with_valid_key PASSED
tests/test_infer.py::test_infer_response_shape PASSED
tests/test_infer.py::test_infer_value_ranges PASSED
tests/test_infer.py::test_infer_reason_is_bilingual PASSED
6 passed
```

- [ ] **Step 8: Commit**

```bash
git add src/api/infer.py src/api/requirements-api.txt src/api/railway.toml tests/
git commit -m "feat(phase2a): FastAPI /infer endpoint + contract tests"
```

---

## Task 7: BFF — add GET /api/items

**Files:**
- Modify: `src/api/server.js`

- [ ] **Step 1: Install Supabase JS client**

```bash
cd src/api && npm install @supabase/supabase-js node-fetch
```

- [ ] **Step 2: Replace `src/api/server.js` entirely**

```javascript
import express from 'express'
import cors from 'cors'
import { createClient } from '@supabase/supabase-js'

const app = express()
app.use(cors())
app.use(express.json())

const PORT = process.env.PORT || 3001

// ── Supabase client ─────────────────────────────────────────────────────────
const supabase = createClient(
  process.env.SUPABASE_URL || '',
  process.env.SUPABASE_ANON_KEY || ''
)

// ── Idempotency set for approve ──────────────────────────────────────────────
const approved = new Set()

function zmkdConditionRecord() {
  return String(Math.floor(Math.random() * 9_000_000_000) + 1_000_000_000).padStart(10, '0')
}

function isoDate(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().split('T')[0]
}

// ── GET /api/items — query Supabase + call FastAPI /infer per item ───────────
app.get('/api/items', async (req, res) => {
  const railwayUrl = process.env.RAILWAY_URL
  const inferApiKey = process.env.INFER_API_KEY

  if (!railwayUrl || !inferApiKey) {
    // Phase 1 fallback: return empty so frontend shows empty state
    return res.status(503).json({ error: 'ML inference not configured' })
  }

  const { data: items, error } = await supabase
    .from('inventory_features')
    .select('*')

  if (error) {
    console.error('Supabase error:', error)
    return res.status(502).json({ error: 'Failed to fetch items' })
  }

  const enriched = await Promise.all(
    items.map(async (item) => {
      try {
        const inferRes = await fetch(`${railwayUrl}/infer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-API-Key': inferApiKey },
          body: JSON.stringify({
            item_id:            item.item_id,
            inventory_age_days: item.inventory_age_days,
            stock_pressure:     item.stock_pressure,
            hour_of_day:        item.hour_of_day,
            sales_velocity_7d:  item.sales_velocity_7d,
            weather_signal:     item.weather_signal,
            price_history_7d:   item.price_history_7d,
          }),
        })
        const ml = await inferRes.json()
        return { ...item, ...ml }
      } catch (err) {
        console.error(`/infer failed for ${item.item_id}:`, err)
        return null
      }
    })
  )

  res.json(enriched.filter(Boolean))
})

// ── POST /api/approve ────────────────────────────────────────────────────────
app.post('/api/approve', (req, res) => {
  const { item_id, discount_pct, manager_override = false } = req.body

  if (!item_id || discount_pct === undefined) {
    return res.status(400).json({ error: 'item_id and discount_pct required' })
  }
  if (discount_pct > 0.5 && !manager_override) {
    return res.status(403).json({ error: 'manager_approval_required', discount_pct })
  }
  if (approved.has(item_id)) {
    return res.json({ status: 'already_applied', condition_record: null })
  }

  approved.add(item_id)
  res.json({
    status: 'zmkd_queued',
    condition_record: zmkdConditionRecord(),
    condition_type: 'ZMKD',
    table: 'A004',
    discount_pct,
    valid_from: isoDate(0),
    valid_to: isoDate(1),
  })
})

// ── POST /api/reject ─────────────────────────────────────────────────────────
app.post('/api/reject', (req, res) => {
  const { item_id, reason_code = 'associate_judgement' } = req.body
  if (!item_id) return res.status(400).json({ error: 'item_id required' })
  res.json({ status: 'rejected', item_id, reason_code })
})

app.listen(PORT, () => console.log(`BFF running on http://localhost:${PORT}`))
```

- [ ] **Step 3: Add env vars to `src/api/.env`**

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
RAILWAY_URL=http://localhost:8000   # local FastAPI during dev
INFER_API_KEY=<same key used in FastAPI .env>
```

- [ ] **Step 4: Smoke test locally**

In terminal 1:
```bash
cd src/api && MODEL_DIR=../../models uvicorn infer:app --port 8000
```

In terminal 2:
```bash
cd src/api && npm run dev
```

In terminal 3:
```bash
curl http://localhost:3001/api/items
```

Expected: JSON array of 12 items each containing `expiry_risk`, `discount_pct`, `confidence`, `reason_fr`, `reason_nl`.

- [ ] **Step 5: Commit**

```bash
git add src/api/server.js src/api/package.json src/api/package-lock.json
git commit -m "feat(phase2a): BFF GET /api/items — Supabase + FastAPI /infer"
```

---

## Task 8: App.jsx — load items from API

**Files:**
- Modify: `src/app/src/App.jsx`

- [ ] **Step 1: Replace `App.jsx`**

```jsx
import { useState, useEffect } from 'react'
import RecommendationCard from './components/RecommendationCard'
import ConfirmationBanner from './components/ConfirmationBanner'
import EmptyState from './components/EmptyState'
import ErrorState from './components/ErrorState'
import { postApprove, postReject } from './lib/api'
import strings from './lib/i18n'

export default function App() {
  const [lang, setLang] = useState('fr')
  const t = strings[lang]

  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [dismissed, setDismissed] = useState(new Set())
  const [banner, setBanner] = useState(null)
  const [error, setError] = useState(false)
  const [offline, setOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const on = () => setOffline(false)
    const off = () => setOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])

  useEffect(() => {
    fetch('/api/items')
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json() })
      .then(items => {
        const sorted = items
          .filter(item => item.shelf_life_hours < 8 && item.stock > 10)
          .sort((a, b) => a.shelf_life_hours - b.shelf_life_hours)
        setQueue(sorted)
        setLoading(false)
      })
      .catch(() => { setError(true); setLoading(false) })
  }, [])

  const visibleQueue = queue.filter(item => !dismissed.has(item.item_id))

  async function handleApprove(item) {
    if (dismissed.has(item.item_id)) { setBanner({ message: t.alreadyApplied, sub: null }); return }
    try {
      const data = await postApprove(item.item_id, item.discount_pct)
      if (data.status === 'already_applied') { setBanner({ message: t.alreadyApplied, sub: null }); return }
      setDismissed(prev => new Set([...prev, item.item_id]))
      setBanner({
        message: t.synced,
        sub: data.condition_record ? t.syncedRef(data.condition_record) : null,
        itemId: item.item_id,
      })
      setError(false)
    } catch { setError(true) }
  }

  async function handleReject(item) {
    try {
      await postReject(item.item_id)
      setDismissed(prev => new Set([...prev, item.item_id]))
      setBanner({ message: t.rejected, sub: null })
      setError(false)
    } catch { setError(true) }
  }

  function handleUndo() {
    if (!banner?.itemId) return
    setDismissed(prev => { const next = new Set(prev); next.delete(banner.itemId); return next })
    setBanner(null)
  }

  function handleRetry() { setError(false); setQueue([]); setLoading(true) }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between sticky top-0 z-40">
        <h1 className="font-bold text-slate-900 text-lg">{t.appTitle}</h1>
        <div className="flex items-center gap-3">
          {offline && (
            <span className="text-xs text-amber-600 font-medium bg-amber-50 px-2.5 py-1 rounded-full">Offline</span>
          )}
          <button
            onClick={() => setLang(l => l === 'fr' ? 'nl' : 'fr')}
            className="text-xs font-semibold text-slate-500 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-lg transition-colors"
          >
            {t.langToggle}
          </button>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-4 py-4 space-y-3">
        {error ? (
          <ErrorState t={t} onRetry={handleRetry} />
        ) : loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 border-2 border-slate-300 border-t-green-600 rounded-full animate-spin" />
          </div>
        ) : visibleQueue.length === 0 ? (
          <EmptyState t={t} />
        ) : (
          visibleQueue.map(item => (
            <RecommendationCard
              key={item.item_id}
              item={item}
              lang={lang}
              t={t}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))
        )}
      </main>

      {banner && (
        <ConfirmationBanner
          key={banner.message + (banner.sub || '')}
          message={banner.message}
          subMessage={banner.sub}
          onUndo={banner.itemId ? handleUndo : null}
          t={t}
        />
      )}

      {offline && (
        <div className="fixed top-14 left-4 right-4 z-50">
          <div className="bg-amber-500 text-white text-xs font-medium text-center py-1.5 rounded-lg">
            {t.offlineToast}
          </div>
        </div>
      )}
    </div>
  )
}
```

Note: `handleApprove` now receives `item` only (not `item, rec`) — `discount_pct` comes from `item` directly since it's returned by `/api/items`.

- [ ] **Step 2: Verify local dev still works**

```bash
cd src/app && npm run dev
```

Expected: app loads, shows spinner, then 12 items (assuming BFF + FastAPI running locally).

- [ ] **Step 3: Commit**

```bash
git add src/app/src/App.jsx
git commit -m "feat(phase2a): App.jsx loads items from GET /api/items"
```

---

## Task 9: Enhanced card — expiry risk bar + SHAP reason

**Files:**
- Modify: `src/app/src/lib/i18n.js`
- Modify: `src/app/src/components/RecommendationCard.jsx`
- Modify: `src/app/src/components/DetailView.jsx`

- [ ] **Step 1: Add i18n keys to `src/app/src/lib/i18n.js`**

In the `fr` object, after `detailAI`:
```js
    expiryRiskLabel: 'Risque expiration',
```

In the `nl` object, after `detailAI`:
```js
    expiryRiskLabel: 'Vervalrisico',
```

- [ ] **Step 2: Replace `src/app/src/components/RecommendationCard.jsx`**

```jsx
import { useState } from 'react'
import DetailView from './DetailView'

export default function RecommendationCard({ item, lang, t, onApprove, onReject }) {
  const [expanded, setExpanded] = useState(false)

  const name = lang === 'fr' ? item.name_fr : item.name_nl
  const displayName = name.length > 42
    ? name.slice(0, 42).replace(/\s+\S*$/, '') + '…'
    : name

  const discount_pct = item.discount_pct ?? 0
  const expiry_risk  = item.expiry_risk  ?? 0
  const confidence   = item.confidence   ?? 0
  const recommended_price = +(item.current_price * (1 - discount_pct)).toFixed(2)
  const manager_required  = discount_pct > 0.5
  const reason = lang === 'fr' ? (item.reason_fr ?? '') : (item.reason_nl ?? '')

  const discountColor = discount_pct >= 0.40
    ? 'bg-red-100 text-red-700'
    : discount_pct >= 0.30
      ? 'bg-orange-100 text-orange-700'
      : 'bg-yellow-100 text-yellow-700'

  const confidenceColor = confidence < 0.5
    ? 'text-red-600'
    : confidence < 0.75
      ? 'text-yellow-600'
      : 'text-green-600'

  const riskPct = Math.round(expiry_risk * 100)
  const riskBarColor = expiry_risk >= 0.75
    ? 'from-orange-400 to-red-500'
    : expiry_risk >= 0.50
      ? 'from-yellow-400 to-orange-400'
      : 'from-green-400 to-yellow-400'

  if (expanded) {
    return (
      <DetailView
        item={item}
        lang={lang}
        t={t}
        onApprove={onApprove}
        onReject={onReject}
        onClose={() => setExpanded(false)}
      />
    )
  }

  return (
    <div
      className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 cursor-pointer active:scale-[0.98] transition-transform"
      onClick={() => setExpanded(true)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-900 text-sm leading-snug truncate">{displayName}</p>
          {reason && <p className="text-xs text-slate-500 mt-1 truncate">{reason}</p>}
        </div>
        <span className={`shrink-0 text-xs font-bold px-2 py-1 rounded-full ${discountColor}`}>
          {t.discountLabel(discount_pct)}
        </span>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <div className="flex items-baseline gap-1">
          <span className="text-slate-400 line-through text-sm">€{item.current_price.toFixed(2)}</span>
          <span className="text-slate-900 font-bold text-lg">€{recommended_price.toFixed(2)}</span>
        </div>
        <div className="flex-1" />
        <span className={`text-xs font-medium ${confidenceColor}`}>
          {t.confidence(confidence)}
        </span>
        <span className="text-xs text-slate-400">{t.expiryLabel(item.shelf_life_hours)}</span>
      </div>

      {/* Expiry risk bar — new in Phase 2A */}
      <div className="mt-3">
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>{t.expiryRiskLabel}</span>
          <span className={expiry_risk >= 0.75 ? 'text-red-500 font-semibold' : 'text-slate-500'}>
            {riskPct} %
          </span>
        </div>
        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${riskBarColor} transition-all`}
            style={{ width: `${riskPct}%` }}
          />
        </div>
      </div>

      {confidence < 0.5 && (
        <p className="mt-2 text-xs text-red-600 font-medium">⚠ {t.lowConfidence}</p>
      )}
      {manager_required && (
        <p className="mt-2 text-xs text-purple-600 font-medium">👤 {t.managerRequired}</p>
      )}

      <div className="mt-4 flex gap-2" onClick={e => e.stopPropagation()}>
        <button
          onClick={() => onApprove(item)}
          className="flex-1 bg-green-600 hover:bg-green-700 active:bg-green-800 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors"
        >
          {t.apply}
        </button>
        <button
          onClick={() => onReject(item)}
          className="flex-1 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-700 text-sm font-semibold py-2.5 rounded-xl transition-colors"
        >
          {t.reject}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update `src/app/src/components/DetailView.jsx`**

Replace the `reason` display and add the expiry risk bar. Full replacement:

```jsx
export default function DetailView({ item, lang, t, onApprove, onReject, onClose }) {
  const name = lang === 'fr' ? item.name_fr : item.name_nl
  const discount_pct = item.discount_pct ?? 0
  const expiry_risk  = item.expiry_risk  ?? 0
  const confidence   = item.confidence   ?? 0
  const recommended_price = +(item.current_price * (1 - discount_pct)).toFixed(2)
  const manager_required  = discount_pct > 0.5
  const reason = lang === 'fr' ? (item.reason_fr ?? '') : (item.reason_nl ?? '')
  const riskPct = Math.round(expiry_risk * 100)

  const discountColor = discount_pct >= 0.40
    ? 'bg-red-100 text-red-700'
    : discount_pct >= 0.30
      ? 'bg-orange-100 text-orange-700'
      : 'bg-yellow-100 text-yellow-700'

  const confidenceColor = confidence < 0.5
    ? 'text-red-600'
    : confidence < 0.75
      ? 'text-yellow-600'
      : 'text-green-600'

  const riskBarColor = expiry_risk >= 0.75
    ? 'from-orange-400 to-red-500'
    : expiry_risk >= 0.50
      ? 'from-yellow-400 to-orange-400'
      : 'from-green-400 to-yellow-400'

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-start gap-3 mb-4">
        <button
          onClick={onClose}
          className="shrink-0 text-slate-400 hover:text-slate-600 text-xl leading-none mt-0.5"
          aria-label="Close"
        >
          ←
        </button>
        <p className="font-semibold text-slate-900 text-base leading-snug">{name}</p>
      </div>

      {reason && (
        <div className="bg-slate-50 rounded-xl p-4 mb-4">
          <p className="text-sm text-slate-600 leading-relaxed">{reason}</p>
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-baseline gap-2">
          <span className="text-slate-400 line-through text-base">€{item.current_price.toFixed(2)}</span>
          <span className="text-slate-900 font-bold text-2xl">€{recommended_price.toFixed(2)}</span>
        </div>
        <span className={`text-sm font-bold px-2.5 py-1 rounded-full ${discountColor}`}>
          {t.discountLabel(discount_pct)}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4 text-center">
        <div className="bg-slate-50 rounded-xl p-3">
          <p className="text-xs text-slate-500 mb-1">{t.detailStock}</p>
          <p className="font-semibold text-slate-900 text-sm">{t.stockLabel(item.stock)}</p>
        </div>
        <div className="bg-slate-50 rounded-xl p-3">
          <p className="text-xs text-slate-500 mb-1">{t.detailExpiry}</p>
          <p className="font-semibold text-slate-900 text-sm">{t.expiryLabel(item.shelf_life_hours)}</p>
        </div>
        <div className="bg-slate-50 rounded-xl p-3">
          <p className="text-xs text-slate-500 mb-1">{t.detailAI}</p>
          <p className={`font-semibold text-sm ${confidenceColor}`}>{t.confidence(confidence)}</p>
        </div>
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>{t.expiryRiskLabel}</span>
          <span className={expiry_risk >= 0.75 ? 'text-red-500 font-semibold' : ''}>{riskPct} %</span>
        </div>
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${riskBarColor}`}
            style={{ width: `${riskPct}%` }}
          />
        </div>
      </div>

      {confidence < 0.5 && (
        <p className="mb-3 text-sm text-red-600 font-medium bg-red-50 rounded-xl px-4 py-2.5">
          ⚠ {t.lowConfidence}
        </p>
      )}
      {manager_required && (
        <p className="mb-3 text-sm text-purple-600 font-medium bg-purple-50 rounded-xl px-4 py-2.5">
          👤 {t.managerRequired}
        </p>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => onApprove(item)}
          className="flex-1 bg-green-600 hover:bg-green-700 active:bg-green-800 text-white text-sm font-semibold py-3 rounded-xl transition-colors"
        >
          {t.apply}
        </button>
        <button
          onClick={() => onReject(item)}
          className="flex-1 bg-slate-100 hover:bg-slate-200 active:bg-slate-300 text-slate-700 text-sm font-semibold py-3 rounded-xl transition-colors"
        >
          {t.reject}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run lint**

```bash
cd src/app && npm run lint
```

Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add src/app/src/lib/i18n.js src/app/src/components/RecommendationCard.jsx src/app/src/components/DetailView.jsx
git commit -m "feat(phase2a): enhanced card — expiry risk bar + SHAP reason"
```

---

## Task 10: Deploy FastAPI to Railway

- [ ] **Step 1: Create Railway project**

Install Railway CLI: `npm i -g @railway/cli` then `railway login`.

```bash
cd src/api && railway init
```

Select "Empty project" → name `ahold-poc-infer`.

- [ ] **Step 2: Set Railway env vars**

```bash
railway variables set INFER_API_KEY=<your-key>
railway variables set SUPABASE_URL=<your-url>
railway variables set SUPABASE_ANON_KEY=<your-key>
```

- [ ] **Step 3: Deploy**

```bash
cd src/api && railway up
```

Railway detects `railway.toml` and runs `uvicorn infer:app --host 0.0.0.0 --port $PORT`.

Expected: deploy succeeds, Railway shows URL like `https://ahold-poc-infer.up.railway.app`.

- [ ] **Step 4: Verify health endpoint**

```bash
curl https://ahold-poc-infer.up.railway.app/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 5: Smoke-test /infer**

```bash
curl -X POST https://ahold-poc-infer.up.railway.app/infer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-key>" \
  -d '{"item_id":"SKU-002","inventory_age_days":2,"stock_pressure":0.72,"hour_of_day":17,"sales_velocity_7d":2.8,"weather_signal":0.3,"price_history_7d":[9.99,9.99,9.99,9.99,10.49,10.49,9.99]}'
```

Expected: JSON with `expiry_risk`, `discount_pct`, `confidence`, `reason_fr`, `reason_nl`.

- [ ] **Step 6: Commit Railway config**

```bash
git add src/api/railway.toml
git commit -m "chore(phase2a): Railway deploy config for FastAPI"
```

---

## Task 11: Wire env vars + production deploy

- [ ] **Step 1: Set Vercel env vars for BFF**

```bash
cd src/api
vercel env add RAILWAY_URL production
# Paste: https://ahold-poc-infer.up.railway.app

vercel env add INFER_API_KEY production
# Paste: <your-key>

vercel env add SUPABASE_URL production
# Paste: https://xxxx.supabase.co

vercel env add SUPABASE_ANON_KEY production
# Paste: eyJ...
```

- [ ] **Step 2: Deploy to Vercel production**

```bash
cd src/app && vercel --prod --yes
```

- [ ] **Step 3: End-to-end smoke test on production URL**

Open https://app-blond-ten-78.vercel.app in browser.

Verify:
- App loads (spinner → 12 cards)
- Each card shows expiry risk bar
- Reason text shows 3 French tokens (e.g. "stock élevé · fin de journée · ventes en baisse")
- Discount shows precise % (e.g. "−31.2 %", not "−30 %")
- Tap card → detail view shows expiry risk bar + reason block
- Approve one item → green banner with ZMKD ref + Annuler button visible for 30s
- Switch to NL → reason shows Dutch tokens

- [ ] **Step 4: Commit any final fixes, tag release**

```bash
git add -p  # stage only intentional changes
git commit -m "feat(phase2a): Phase 2A live — XGBoost M2+M3 + enhanced card"
git tag phase2a-demo
```
