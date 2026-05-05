# ml/prepare_dataset.py
"""Script độc lập để kiểm tra dataset trước khi train."""
from ml.features import build_training_data

if __name__ == "__main__":
    df = build_training_data()
    print(f"Dataset shape: {df.shape}")
    print(f"Label distribution:\n{df['label'].value_counts().sort_index()}")
    print(f"\nSample features:\n{df.head(3).to_string()}")
    print(f"\nMissing values:\n{df.isnull().sum()}")