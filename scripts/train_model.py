"""BrawlBuddy Model Training CLI.

Extracts match data, trains baseline Logistic Regression and LightGBM models,
evaluates using temporal validation, and serializes the model artifact.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ml.database import MetaDatabase
from app.ml.model import BrawlerOutcomePredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("brawlbuddy.train")


def main() -> None:
    db_path = PROJECT_ROOT / "data" / "brawl_meta.db"
    database = MetaDatabase(db_path)
    predictor = BrawlerOutcomePredictor(database)

    print("\n=== BrawlBuddy ML Training Pipeline ===")
    print("[*] Extracting 3v3 team compositions from SQLite database...")
    result = predictor.train_and_evaluate()

    if result.get("status") == "insufficient_data":
        print(f"[-] Insufficient training data ({result.get('samples')} samples). Minimum 50 required.")
        return

    samples = result["samples"]
    lgbm = result["lgbm"]
    baseline = result["baseline_lr"]

    print(f"[+] Successfully extracted {samples} symmetrical match observations.")
    print(f"    - Training samples: {lgbm['train_samples']}")
    print(f"    - Temporal test samples: {lgbm['test_samples']}")
    print("\n--- Evaluation Metrics Comparison ---")
    print(f"{'Metric':<16} | {'Baseline (Logistic Reg)':<24} | {'Model A (LightGBM)':<20}")
    print("-" * 66)
    print(f"{'Accuracy':<16} | {baseline['accuracy']:<24.4f} | {lgbm['accuracy']:<20.4f}")
    print(f"{'ROC-AUC':<16} | {baseline['roc_auc']:<24.4f} | {lgbm['roc_auc']:<20.4f}")
    print(f"{'Log Loss':<16} | {baseline['log_loss']:<24.4f} | {lgbm['log_loss']:<20.4f}")
    print(f"{'Brier Score':<16} | {baseline['brier_score']:<24.4f} | {lgbm['brier_score']:<20.4f}")
    print("-" * 66)
    print(f"[+] Model serialized and saved to: {predictor.model_dir / 'lgbm_v1.pkl'}")
    print(f"[+] Metadata saved to: {predictor.model_dir / 'lgbm_v1_meta.json'}\n")


if __name__ == "__main__":
    main()
