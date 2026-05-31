import os
import json
import joblib
import logging
import numpy as np
import pandas as pd

from datetime import datetime, timezone

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)

from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

from ml.features import FEATURES, build_dataset

logger = logging.getLogger(__name__)

MODEL_DIR = "ml/models"

BEST_MODEL_PATH = os.path.join(MODEL_DIR, "best_model.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")


# =========================
# METRICS
# =========================
def compute_metrics(y_true, y_pred):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "recall": float(
            recall_score(y_true, y_pred, average="weighted", zero_division=0)
        ),
        "f1": float(f1_score(y_true, y_pred, average="weighted")),
    }


# =========================
# ONLY 3 MODELS
# =========================
def build_models(num_classes):
    return {
        "XGBoost": XGBClassifier(
            objective="multi:softmax",
            num_class=num_classes,
            n_estimators=200,
            max_depth=8,
            learning_rate=0.05,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1
        ),

        "LightGBM": LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=8,
            random_state=42,
            verbose=-1
        ),

        "CatBoost": CatBoostClassifier(
            iterations=300,
            depth=8,
            learning_rate=0.05,
            verbose=0,
            random_state=42
        )
    }


# =========================
# DATA LOADING
# =========================
def show_sample():
    df = build_dataset(n_days=None, roads_limit=None)

    if df is None or len(df) < 100:
        logger.error("Không đủ dữ liệu")
        return None

    df = df.sort_values("timestamp").reset_index(drop=True)

    split_idx = int(len(df) * 0.8)

    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    X_train = train_df[FEATURES].values
    y_train = train_df["label"].values.astype(int)

    X_test = test_df[FEATURES].values
    y_test = test_df["label"].values.astype(int)

    logger.info("Train size=%d | Test size=%d", len(train_df), len(test_df))

    return X_train, y_train, X_test, y_test


# =========================
# TRAIN
# =========================
def train():
    data = show_sample()
    if data is None:
        return

    X_train, y_train, X_test, y_test = data

    num_classes = len(np.unique(y_train))
    models = build_models(num_classes)

    os.makedirs(MODEL_DIR, exist_ok=True)

    results = []

    best_model = None
    best_model_name = None
    best_f1 = -1

    for name, model in models.items():

        logger.info("=" * 60)
        logger.info("TRAINING %s", name)
        logger.info("=" * 60)

        try:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            metrics = compute_metrics(y_test, y_pred)

            logger.info("\n%s", classification_report(y_test, y_pred))
            logger.info("\nConfusion Matrix:\n%s", confusion_matrix(y_test, y_pred))

            logger.info("F1: %.4f", metrics["f1"])

            results.append({
                "model": name,
                **metrics
            })

            if metrics["f1"] > best_f1:
                best_f1 = metrics["f1"]
                best_model = model
                best_model_name = name

        except Exception as e:
            logger.exception("Model %s failed: %s", name, e)

    # =========================
    # SAVE RESULTS
    # =========================
    results_df = pd.DataFrame(results).sort_values("f1", ascending=False)

    logger.info("\nFINAL RANKING\n%s", results_df)

    if best_model is None:
        logger.error("Không model nào train thành công")
        return

    joblib.dump(best_model, BEST_MODEL_PATH)

    metrics_out = {
        "best_model": best_model_name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES,
        "results": results_df.to_dict(orient="records")
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_out, f, indent=2, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info("BEST MODEL = %s", best_model_name)
    logger.info("BEST F1 = %.4f", best_f1)
    logger.info("Saved model -> %s", BEST_MODEL_PATH)
    logger.info("Saved metrics -> %s", METRICS_PATH)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    train()