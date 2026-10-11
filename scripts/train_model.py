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
        print(result['message'])
        return

    print(f"[+] Trained {result['samples']} mirrored observations; champion: {result['best_model']}")
    for row in result['benchmark']:
        print(f"{row['name']}: CV log loss {row['cv_log_loss_mean']:.4f}; holdout AUC {row['test_roc_auc']:.4f}")
    print(f"[+] Model saved to {predictor.model_dir / (predictor.version + '.pkl')}")


if __name__ == "__main__":
    main()
