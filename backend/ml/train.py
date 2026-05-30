# ml/train.py
import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, accuracy_score

from ml.features import build_training_data
from ml.constants import FEATURES

MODEL_DIR  = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH  = os.path.join(MODEL_DIR, "rf_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")


def retrain_model(db_session=None) -> dict:
    """
    Train/retrain model. Trả về metrics dict.
    Gọi với db_session=None để dùng mock data (dev mode).
    """
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Bắt đầu build dataset...")
    df = build_training_data(db_session)

    X = df[FEATURES].values
    y = df["label"].values
    print(f"  → Dataset: {len(df):,} records, {X.shape[1]} features")

    # Train/test split (giữ thứ tự thời gian)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, shuffle=False
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    # GridSearch (optimized para giảm thời gian train)
    print("  → Đang GridSearch...")
    param_grid = {
        "n_estimators": [100, 150],  # Giảm từ [100, 200]
        "max_depth":    [5, 8],      # Giảm từ [5, 10, None]
        "min_samples_split": [2],    # Giảm từ [2, 5]
    }
    rf = RandomForestClassifier(random_state=42, n_jobs=-1)
    grid_search = GridSearchCV(
        rf, param_grid, cv=3,  # Giảm từ cv=5
        scoring="f1_weighted", verbose=0, n_jobs=-1
    )
    grid_search.fit(X_train_scaled, y_train)
    best_model = grid_search.best_estimator_

    # Evaluate — train set
    y_train_pred = best_model.predict(X_train_scaled)
    train_acc  = accuracy_score(y_train, y_train_pred)
    train_f1   = f1_score(y_train, y_train_pred, average="weighted")
    train_rmse = float(np.sqrt(np.mean((y_train - y_train_pred) ** 2)))

    # Evaluate — test set
    y_pred = best_model.predict(X_test_scaled)
    acc    = accuracy_score(y_test, y_pred)
    f1     = f1_score(y_test, y_pred, average="weighted")
    rmse   = float(np.sqrt(np.mean((y_test - y_pred) ** 2)))

    print(f"  → Best params: {grid_search.best_params_}")
    print(f"  → [Train] Accuracy: {train_acc:.3f} | F1: {train_f1:.3f} | RMSE: {train_rmse:.3f}")
    print(f"  → [Test]  Accuracy: {acc:.3f}       | F1: {f1:.3f}       | RMSE: {rmse:.3f}")

    # Kiểm tra ngưỡng
    if f1 < 0.70:
        print(f"  ⚠️  WARNING: F1={f1:.3f} < 0.70 — model chưa đạt ngưỡng!")

    # Overfit detection
    if train_f1 - f1 > 0.10:
        print(f"  ⚠️  WARNING: Overfit — Train F1={train_f1:.3f} vs Test F1={f1:.3f} (gap={train_f1 - f1:.3f})")

    # Feature importance log
    importances = best_model.feature_importances_
    feat_imp = sorted(zip(FEATURES, importances), key=lambda x: -x[1])
    print("  → Feature importance (top 5):")
    for feat, imp in feat_imp[:5]:
        print(f"       {feat:<25} {imp:.4f}")

    # Lưu model và scaler
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    # Lưu metrics
    metrics = {
        "train": {
            "accuracy":    round(train_acc, 4),
            "f1_weighted": round(train_f1, 4),
            "rmse":        round(train_rmse, 4),
        },
        "test": {
            "accuracy":    round(acc, 4),
            "f1_weighted": round(f1, 4),
            "rmse":        round(rmse, 4),
        },
        "best_params":  grid_search.best_params_,
        "n_train":      len(X_train),
        "n_test":       len(X_test),
        "trained_at":   datetime.utcnow().isoformat(),
    }
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Model đã lưu → {MODEL_PATH}")
    print(f"  ✅ Metrics đã lưu → {METRICS_PATH}")
    return metrics

# ml/train.py — thêm vào cuối file, sau hàm retrain_model()

def retrain_and_reload(db_session=None) -> dict:
    """
    Wrap toàn bộ flow: retrain → hot-reload model vào service.
    Gọi hàm này từ scheduled job (Task #29b).
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("🔄 [AutoRetrain] Bắt đầu retrain...")
    
    try:
        # Bước 1: Train lại model
        metrics = retrain_model(db_session)
        logger.info(
            f"✅ [AutoRetrain] Train xong — "
            f"Train F1={metrics['train']['f1_weighted']:.3f} | "
            f"Test F1={metrics['test']['f1_weighted']:.3f}"
        )

        # Bước 2: Hot-reload vào PredictionService (không restart server)
        try:
            from services.prediction_service import prediction_service
            prediction_service.reload_model()
            logger.info("✅ [AutoRetrain] Hot-reload model thành công")
        except Exception as e:
            logger.error(f"⚠️  [AutoRetrain] Hot-reload thất bại: {e}")

        # Bước 3: Ghi timestamp retrain vào Redis (optional, để monitor)
        try:
            import redis, os
            from datetime import datetime
            r = redis.Redis(
                host=os.getenv("REDIS_HOST", "redis"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True
            )
            r.set("ml:retrain:last", datetime.utcnow().isoformat())
            logger.info("✅ [AutoRetrain] Đã ghi timestamp vào Redis")
        except Exception as e:
            logger.warning(f"⚠️  [AutoRetrain] Ghi Redis thất bại (không ảnh hưởng): {e}")

        return {"status": "success", "metrics": metrics}

    except Exception as e:
        logger.error(f"❌ [AutoRetrain] Thất bại: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}

if __name__ == "__main__":
    retrain_model(db_session=None)  # chạy với mock data