"""
ml/train.py — Train and cache the Next Big Hit classifier.
Uses Random Forest. Saves model to ml/nbh_model.pkl.
Run: python ml/train.py   OR   called automatically from page 3.
"""
import os, sys, pickle
import numpy as np
import pandas as pd

MODEL_PATH = os.path.join(os.path.dirname(__file__), "nbh_model.pkl")

FEATURE_NAMES = [
    "length", "rental_rate", "replacement_cost",
    "rental_duration", "num_actors",
    "has_behind_scenes", "has_commentaries", "has_deleted_scenes", "has_trailers",
    "genre_enc", "rating_enc",
]

GENRE_MAP = {
    "Action":1,"Animation":2,"Children":3,"Classics":4,"Comedy":5,
    "Documentary":6,"Drama":7,"Family":8,"Foreign":9,"Games":10,
    "Horror":11,"Music":12,"New":13,"Sci-Fi":14,"Sports":15,"Travel":16,
}
RATING_MAP = {"G":1,"PG":2,"PG-13":3,"R":4,"NC-17":5}


def build_features(row) -> list:
    """Convert row to feature vector"""
    if isinstance(row, dict):
        sf = str(row.get("special_features", "") or "").lower()
        genre = row.get("genre_name", "Drama")
        rating = row.get("rating", "PG")
        return [
            float(row.get("length") or 90),
            float(row.get("rental_rate") or 2.99),
            float(row.get("replacement_cost") or 19.99),
            float(row.get("rental_duration") or 3),
            float(row.get("num_actors") or 5),
            1.0 if "behind" in sf else 0.0,
            1.0 if "comment" in sf else 0.0,
            1.0 if "deleted" in sf else 0.0,
            1.0 if "trailer" in sf else 0.0,
            float(GENRE_MAP.get(genre, 7)),
            float(RATING_MAP.get(rating, 2)),
        ]
    else:
        # Handle Series
        sf = str(row.get("special_features", "") or "").lower()
        genre = row.get("genre_name", "Drama")
        rating = row.get("rating", "PG")
        return [
            float(row.get("length", 90)),
            float(row.get("rental_rate", 2.99)),
            float(row.get("replacement_cost", 19.99)),
            float(row.get("rental_duration", 3)),
            float(row.get("num_actors", 5)),
            1.0 if "behind" in sf else 0.0,
            1.0 if "comment" in sf else 0.0,
            1.0 if "deleted" in sf else 0.0,
            1.0 if "trailer" in sf else 0.0,
            float(GENRE_MAP.get(genre, 7)),
            float(RATING_MAP.get(rating, 2)),
        ]


def train(rows) -> bool:
    """Train Random Forest model"""
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        # Convert to DataFrame if needed
        if isinstance(rows, list):
            df = pd.DataFrame(rows)
        else:
            df = rows
            
        # Build features
        X = np.array([build_features(row) for _, row in df.iterrows()])
        y = np.array([1 if row.get("is_popular") else 0 for _, row in df.iterrows()])
        
        # Check if we have both classes
        if len(set(y)) < 2:
            print("⚠️ Not enough class variety (need both popular and non-popular films) — using dummy model")
            # Create a simple dummy model
            from sklearn.dummy import DummyClassifier
            model = Pipeline([
                ("scaler", StandardScaler()),
                ("clf", DummyClassifier(strategy="most_frequent", random_state=42)),
            ])
        else:
            model = Pipeline([
                ("scaler", StandardScaler()),
                ("clf", RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, class_weight="balanced")),
            ])
        
        model.fit(X, y)
        
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model, f)
        print(f"✅ Model saved to {MODEL_PATH}")
        return True
        
    except Exception as e:
        print(f"❌ Training error: {e}")
        import traceback
        traceback.print_exc()
        return False


def load():
    """Load trained model"""
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        except:
            return None
    return None


def predict(model, row: dict) -> dict:
    """Predict popularity score"""
    try:
        X = np.array([build_features(row)])
        
        # Check if model has predict_proba
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X)[0]
            # If model has 2 classes, proba[1] is positive class
            if len(proba) >= 2:
                score = float(proba[1]) * 100
            else:
                score = float(proba[0]) * 100
        else:
            # Fallback for dummy classifier
            pred = model.predict(X)[0]
            score = 60.0 if pred == 1 else 40.0
        
        # Get feature importances if available
        if hasattr(model.named_steps["clf"], "feature_importances_"):
            importances = model.named_steps["clf"].feature_importances_
            feat_imp = sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
        else:
            # Dummy importances
            feat_imp = [(name, 1.0/len(FEATURE_NAMES)) for name in FEATURE_NAMES]
        
        return {
            "score": round(score, 1),
            "label": "Popular 🔥" if score >= 60 else "Moderate 📊" if score >= 40 else "Niche 💤",
            "color": "#059669" if score >= 60 else "#d97706" if score >= 40 else "#dc2626",
            "feature_importance": feat_imp[:8],
        }
    except Exception as e:
        print(f"Prediction error: {e}")
        return {"score": 50.0, "label": "Moderate 📊", "color": "#d97706", "feature_importance": []}


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from db import query_df
    
    print("Loading film features from database...")
    rows = query_df("SELECT * FROM summary_film_features WHERE genre_name IS NOT NULL")
    
    if rows:
        print(f"Found {len(rows)} films")
        train(rows)
    else:
        print("No data found. Run refresh_summaries() first.")