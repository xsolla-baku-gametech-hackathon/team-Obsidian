"""Exploratory Steam success model aligned with the current API contract.

This file is intentionally not imported by the production API. It trains from the
Kaggle Steam catalog, but its feature builder also accepts the nested JSON returned
by `POST /api/v1/steam/games/inspect`, including upcoming games where reviews and
current-player data are unavailable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

DATASET_ID = "hubertsidorowicz/steam-games-dataset-daily-updates"
MODEL_VERSION = "steam-success-experiment-v2"

CATEGORICAL_FEATURES = ["primary_genre", "business_model"]
NUMERIC_FEATURES = [
    "price_usd",
    "release_month",
    "release_dayofweek",
    "genre_count",
    "category_count",
    "screenshot_count",
    "movie_count",
    "has_price",
    "windows",
    "mac",
    "linux",
]
FEATURE_COLUMNS = [*CATEGORICAL_FEATURES, *NUMERIC_FEATURES]


def download_dataset() -> Path:
    import kagglehub

    dataset_path = Path(kagglehub.dataset_download(DATASET_ID))
    return dataset_path / "steam_games.csv"


def _labels(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        labels = []
        for item in value:
            if isinstance(item, dict):
                labels.append(str(item.get("name") or item.get("description") or "").strip())
            else:
                labels.append(str(item).strip())
        return [label for label in labels if label]
    if isinstance(value, dict):
        return [str(key).strip() for key in value if str(key).strip()]

    text = str(value).strip()
    if not text:
        return []
    try:
        return _labels(json.loads(text))
    except json.JSONDecodeError:
        return [part.strip() for part in text.split(",") if part.strip()]


def _first_label(value: Any, fallback: str = "Indie") -> str:
    labels = _labels(value)
    return labels[0] if labels else fallback


def _minor_to_usd(value: Any) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return float(numeric) / 100


def _column(df: pd.DataFrame, name: str, default: Any) -> pd.Series:
    if name in df:
        return df[name]
    return pd.Series(default, index=df.index)


def _boolean_series(df: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    return _column(df, column, default).fillna(default).astype(bool)


def build_training_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build features from the Kaggle catalog without requiring live Steam fields."""
    frame = pd.DataFrame(index=df.index)

    positive = pd.to_numeric(_column(df, "positive", 0), errors="coerce").fillna(0)
    negative = pd.to_numeric(_column(df, "negative", 0), errors="coerce").fillna(0)
    total_reviews = positive + negative
    review_ratio = np.where(total_reviews > 0, positive / total_reviews, 0.5)
    peak_ccu = pd.to_numeric(_column(df, "peak_ccu", 0), errors="coerce").fillna(0)
    success_score = (review_ratio * 50) + np.clip(np.log1p(peak_ccu) * 5, 0, 50)

    release_date = pd.to_datetime(_column(df, "release_date", None), errors="coerce")
    genres = _column(df, "genres", "Indie")
    categories = _column(df, "categories", "")
    price = pd.to_numeric(_column(df, "price", np.nan), errors="coerce")
    price_status = _column(df, "price_status", "").astype(str).str.lower()
    is_free = price_status.eq("free") | pd.to_numeric(price, errors="coerce").fillna(1).eq(0)

    frame["primary_genre"] = genres.apply(_first_label)
    frame["business_model"] = np.where(is_free, "free", "premium")
    frame["price_usd"] = price.fillna(0)
    frame["release_month"] = release_date.dt.month
    frame["release_dayofweek"] = release_date.dt.dayofweek
    frame["genre_count"] = genres.apply(lambda value: len(_labels(value)))
    frame["category_count"] = categories.apply(lambda value: len(_labels(value)))
    frame["screenshot_count"] = pd.to_numeric(_column(df, "screenshots_count", 0), errors="coerce")
    frame["movie_count"] = pd.to_numeric(_column(df, "movies_count", 0), errors="coerce")
    frame["has_price"] = (price.notna() | is_free).astype(int)
    frame["windows"] = _boolean_series(df, "windows", True).astype(int)
    frame["mac"] = _boolean_series(df, "mac").astype(int)
    frame["linux"] = _boolean_series(df, "linux").astype(int)

    return frame[FEATURE_COLUMNS], pd.Series(success_score, name="success_score")


def build_features_from_inspection(payload: dict[str, Any]) -> pd.DataFrame:
    """Build one prediction row from the current Steam inspection response JSON."""
    data = payload.get("data", payload)
    metadata = data.get("metadata", data)
    release = metadata.get("release_date") or {}
    price = metadata.get("price") or {}
    platforms = metadata.get("platforms") or {}

    release_date = pd.to_datetime(release.get("raw"), errors="coerce")
    final_minor = price.get("final_minor")
    is_free = bool(metadata.get("is_free"))

    row = {
        "primary_genre": _first_label(metadata.get("genres")),
        "business_model": "free" if is_free else "premium",
        "price_usd": 0.0 if is_free else _minor_to_usd(final_minor),
        "release_month": release_date.month if not pd.isna(release_date) else np.nan,
        "release_dayofweek": release_date.dayofweek if not pd.isna(release_date) else np.nan,
        "genre_count": len(_labels(metadata.get("genres"))),
        "category_count": len(_labels(metadata.get("categories"))),
        "screenshot_count": len(metadata.get("screenshots") or []),
        "movie_count": len(metadata.get("movies") or []),
        "has_price": int(final_minor is not None or is_free),
        "windows": int(bool(platforms.get("windows"))),
        "mac": int(bool(platforms.get("mac"))),
        "linux": int(bool(platforms.get("linux"))),
    }
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def make_pipeline() -> Pipeline:
    preprocessing = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUMERIC_FEATURES,
            ),
        ]
    )
    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("model", RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)),
        ]
    )


def train(csv_path: Path, artifacts_dir: Path) -> dict[str, Any]:
    df = pd.read_csv(csv_path)
    features, target = build_training_frame(df)
    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=42
    )

    pipeline = make_pipeline()
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / "steam_success_model.joblib"
    metadata_path = artifacts_dir / "steam_success_model.metadata.json"
    joblib.dump(pipeline, model_path)

    metadata = {
        "model_version": MODEL_VERSION,
        "dataset_id": DATASET_ID,
        "feature_columns": FEATURE_COLUMNS,
        "target": "success_score = review_ratio + peak_ccu proxy from historical released games",
        "r2_score": round(float(r2_score(y_test, predictions)), 4),
        "training_rows": int(len(features)),
        "model_path": str(model_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def predict_from_inspection(model_path: Path, inspection_json_path: Path) -> float:
    pipeline = joblib.load(model_path)
    payload = json.loads(inspection_json_path.read_text())
    features = build_features_from_inspection(payload)
    return float(pipeline.predict(features)[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Train or test the exploratory Steam model.")
    parser.add_argument("--csv", type=Path, help="Path to steam_games.csv. Downloads if omitted.")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("ml/artifacts"))
    parser.add_argument("--predict-json", type=Path, help="Inspection response JSON to score.")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("ml/artifacts/steam_success_model.joblib"),
        help="Saved model path for --predict-json.",
    )
    args = parser.parse_args()

    if args.predict_json:
        score = predict_from_inspection(args.model, args.predict_json)
        print(f"Predicted exploratory success score: {score:.2f}")
        return

    csv_path = args.csv or download_dataset()
    metadata = train(csv_path, args.artifacts_dir)
    print(f"Model trained: R2={metadata['r2_score']:.3f}")
    print(f"Saved model: {metadata['model_path']}")


if __name__ == "__main__":
    main()
