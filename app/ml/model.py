from __future__ import annotations

import json
import logging
import pickle
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
import lightgbm as lgb
import xgboost as xgb

from app.ml.database import MetaDatabase
from app.ml.meta_engine import StatisticalMetaEngine

logger = logging.getLogger("brawlbuddy.ml.model")


@dataclass
class ModelMetrics:
    model_name: str
    train_samples: int
    test_samples: int
    accuracy: float
    roc_auc: float
    log_loss: float
    brier_score: float
    trained_at: str
    cv_accuracy: Optional[str] = None
    cv_roc_auc: Optional[str] = None


    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BrawlerOutcomePredictor:
    """Predicts 3v3 match victory probabilities and powers the draft recommendation layer."""

    def __init__(
        self,
        database: MetaDatabase,
        model_dir: Optional[Path] = None,
    ) -> None:
        self.db = database
        self.model_dir = model_dir or Path(self.db.db_path).parent / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.meta_engine = StatisticalMetaEngine(database)
        self.model: Optional[Any] = None
        self.baseline_lr: Optional[LogisticRegression] = None
        self.brawler_ids: list[int] = []
        self.brawler_to_idx: dict[int, int] = {}
        self.mode_to_idx: dict[str, int] = {}
        self.metrics: Optional[ModelMetrics] = None
        self.baseline_metrics: Optional[ModelMetrics] = None
        self.benchmark_results: list[dict[str, Any]] = []
        self.feature_importances: dict[str, Any] = {}
        self.version = "lgbm_v2"


    def _extract_dataset(self) -> pd.DataFrame:
        """Extract clean 3v3 matches from SQLite into symmetrical match observations.
        
        Strictly excludes post-match data (star player, match duration, trophy changes).
        Only uses pre-match information: mode, map, team A brawlers, team B brawlers, power diff.
        """
        with closing(self.db.connect()) as conn:
            # Query only team-based matches (where teams are defined)
            query = """
                SELECT
                    m.match_fingerprint,
                    m.battle_time,
                    m.mode,
                    m.map,
                    m.match_type,
                    m.team_a_avg_power,
                    m.team_b_avg_power,
                    p.team_index,
                    p.brawler_id,
                    p.is_winner
                FROM matches m
                JOIN match_participants p ON m.match_fingerprint = p.match_fingerprint
                WHERE m.team_a_avg_power > 0 AND p.team_index IN (0, 1)
                ORDER BY m.battle_time ASC
            """
            rows = conn.execute(query).fetchall()

        # Group participants by match_fingerprint
        matches_dict: dict[str, dict[str, Any]] = {}
        for r in rows:
            mf = r["match_fingerprint"]
            if mf not in matches_dict:
                matches_dict[mf] = {
                    "match_fingerprint": mf,
                    "battle_time": r["battle_time"],
                    "mode": r["mode"],
                    "map": r["map"],
                    "match_type": r["match_type"],
                    "team_a_avg_power": r["team_a_avg_power"],
                    "team_b_avg_power": r["team_b_avg_power"],
                    "team_0_brawlers": [],
                    "team_1_brawlers": [],
                    "team_0_winner": None,
                }
            t_idx = r["team_index"]
            b_id = r["brawler_id"]
            if t_idx == 0:
                matches_dict[mf]["team_0_brawlers"].append(b_id)
                if r["is_winner"] is not None:
                    matches_dict[mf]["team_0_winner"] = r["is_winner"]
            elif t_idx == 1:
                matches_dict[mf]["team_1_brawlers"].append(b_id)

        # Build symmetrical records
        records = []
        for m in matches_dict.values():
            t0 = m["team_0_brawlers"]
            t1 = m["team_1_brawlers"]
            winner = m["team_0_winner"]
            # We require standard teams (at least 2 brawlers per team, typically 3)
            if len(t0) < 2 or len(t1) < 2 or winner is None:
                continue

            power_diff = m["team_a_avg_power"] - m["team_b_avg_power"]

            # Perspective A (Team 0 vs Team 1)
            records.append({
                "battle_time": m["battle_time"],
                "mode": m["mode"],
                "map": m["map"],
                "match_type": m["match_type"],
                "allies": t0,
                "enemies": t1,
                "power_diff": power_diff,
                "target": int(winner == 1),
            })

            # Perspective B (Team 1 vs Team 0, symmetrical with negated power diff & flipped target)
            records.append({
                "battle_time": m["battle_time"],
                "mode": m["mode"],
                "map": m["map"],
                "match_type": m["match_type"],
                "allies": t1,
                "enemies": t0,
                "power_diff": -power_diff,
                "target": int(winner == 0),
            })

        df = pd.DataFrame(records)
        logger.info("Extracted %d symmetrical match observations", len(df))
        return df

    def _build_feature_matrix(
        self,
        df: pd.DataFrame,
        is_training: bool = True,
    ) -> tuple[np.ndarray, np.ndarray]:
        if is_training:
            # Collect all distinct brawler IDs across allies and enemies
            all_brawlers = set()
            for b_list in df["allies"]:
                all_brawlers.update(b_list)
            for b_list in df["enemies"]:
                all_brawlers.update(b_list)
            self.brawler_ids = sorted(list(all_brawlers))
            self.brawler_to_idx = {b: i for i, b in enumerate(self.brawler_ids)}

            modes = sorted(list(df["mode"].unique()))
            self.mode_to_idx = {m: i for i, m in enumerate(modes)}

        n_samples = len(df)
        n_brawlers = len(self.brawler_ids)
        n_modes = len(self.mode_to_idx)

        # Feature layout:
        # [Allies one-hot (n_brawlers)] + [Enemies one-hot (n_brawlers)] + [Modes one-hot (n_modes)] + [power_diff (1)]
        X = np.zeros((n_samples, (n_brawlers * 2) + n_modes + 1), dtype=np.float32)

        for i, row in df.reset_index(drop=True).iterrows():
            # Allies
            for b in row["allies"]:
                if b in self.brawler_to_idx:
                    X[i, self.brawler_to_idx[b]] = 1.0
            # Enemies
            for b in row["enemies"]:
                if b in self.brawler_to_idx:
                    X[i, n_brawlers + self.brawler_to_idx[b]] = 1.0
            # Mode
            m_idx = self.mode_to_idx.get(row["mode"])
            if m_idx is not None:
                X[i, (n_brawlers * 2) + m_idx] = 1.0
            # Power difference
            X[i, -1] = float(row.get("power_diff", 0.0))

        y = df["target"].values.astype(np.int32)
        return X, y

    def train_and_evaluate(self, n_splits: int = 5) -> dict[str, Any]:
        """Train and benchmark multiple model frameworks with 5-fold cross-validation.
        
        Evaluates:
          1. Baseline Logistic Regression (L2)
          2. Random Forest (Ensemble Trees)
          3. HistGradientBoosting (Histogram GBDT)
          4. XGBoost (Extreme Gradient Boosting)
          5. LightGBM (Tuned GBDT)
          6. Stacking/Voting Ensemble (Multi-Framework Blend)
          
        Picks the best-performing model to maximize accuracy and ROC-AUC.
        """
        import time

        df = self._extract_dataset()
        if len(df) < 50:
            logger.warning("Dataset too small for reliable ML training (%d samples).", len(df))
            return {"status": "insufficient_data", "samples": len(df)}

        # Temporal split: 80% earlier matches for training, 20% latest matches for testing
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        X_train, y_train = self._build_feature_matrix(train_df, is_training=True)
        X_test, y_test = self._build_feature_matrix(test_df, is_training=False)

        # 5-Fold Stratified Cross-Validation
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

        candidate_frameworks = {
            "Baseline Logistic Regression": LogisticRegression(C=0.5, max_iter=250, random_state=42),
            "Random Forest": RandomForestClassifier(n_estimators=120, max_depth=12, min_samples_split=4, random_state=42, n_jobs=-1),
            "HistGradientBoosting": HistGradientBoostingClassifier(max_iter=120, learning_rate=0.05, l2_regularization=0.1, random_state=42),
            "XGBoost": xgb.XGBClassifier(n_estimators=120, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, eval_metric="logloss", random_state=42),
            "LightGBM (Tuned)": lgb.LGBMClassifier(n_estimators=120, max_depth=6, num_leaves=35, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1, random_state=42, verbosity=-1),
        }

        # Add Voting Ensemble
        ensemble = VotingClassifier(
            estimators=[
                ("rf", RandomForestClassifier(n_estimators=120, max_depth=12, min_samples_split=4, random_state=42, n_jobs=-1)),
                ("lgbm", lgb.LGBMClassifier(n_estimators=120, max_depth=6, num_leaves=35, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1, random_state=42, verbosity=-1)),
                ("xgb", xgb.XGBClassifier(n_estimators=120, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, eval_metric="logloss", random_state=42)),
                ("lr", LogisticRegression(C=0.5, max_iter=250, random_state=42)),
            ],
            voting="soft",
            weights=[2.0, 1.5, 1.5, 1.0],
        )
        candidate_frameworks["Ensemble (Multi-Framework Blend)"] = ensemble

        benchmark_list = []
        best_score = -1.0
        best_model_name = ""
        best_model_obj = None

        for name, clf in candidate_frameworks.items():
            t0 = time.time()
            cv_acc, cv_auc, cv_loss, cv_brier = [], [], [], []

            for tr_idx, val_idx in cv.split(X_train, y_train):
                fold_clf = clf
                fold_clf.fit(X_train[tr_idx], y_train[tr_idx])
                probs = fold_clf.predict_proba(X_train[val_idx])[:, 1]
                preds = (probs >= 0.5).astype(int)

                cv_acc.append(float(accuracy_score(y_train[val_idx], preds)))
                cv_auc.append(float(roc_auc_score(y_train[val_idx], probs)))
                cv_loss.append(float(log_loss(y_train[val_idx], probs)))
                cv_brier.append(float(brier_score_loss(y_train[val_idx], probs)))

            # Train on full train split and evaluate on holdout test set
            clf.fit(X_train, y_train)
            test_probs = clf.predict_proba(X_test)[:, 1]
            test_preds = (test_probs >= 0.5).astype(int)
            elapsed = time.time() - t0

            t_acc = round(float(accuracy_score(y_test, test_preds)), 4)
            t_auc = round(float(roc_auc_score(y_test, test_probs)), 4)
            t_loss = round(float(log_loss(y_test, test_probs)), 4)
            t_brier = round(float(brier_score_loss(y_test, test_probs)), 4)

            cv_acc_m = round(float(np.mean(cv_acc)), 4)
            cv_acc_s = round(float(np.std(cv_acc)), 4)
            cv_auc_m = round(float(np.mean(cv_auc)), 4)
            cv_auc_s = round(float(np.std(cv_auc)), 4)

            selection_score = (t_acc * 0.5) + (t_auc * 0.5)
            if selection_score > best_score:
                best_score = selection_score
                best_model_name = name
                best_model_obj = clf

            result_entry = {
                "name": name,
                "framework": "scikit-learn" if "Baseline" in name or "Random" in name or "Hist" in name or "Ensemble" in name else ("LightGBM" if "LightGBM" in name else "XGBoost"),
                "cv_accuracy": f"{cv_acc_m*100:.2f}% ± {cv_acc_s*100:.2f}%",
                "cv_accuracy_mean": cv_acc_m,
                "cv_accuracy_std": cv_acc_s,
                "cv_roc_auc": f"{cv_auc_m:.4f} ± {cv_auc_s:.4f}",
                "cv_roc_auc_mean": cv_auc_m,
                "cv_roc_auc_std": cv_auc_s,
                "cv_log_loss_mean": round(float(np.mean(cv_loss)), 4),
                "cv_brier_score_mean": round(float(np.mean(cv_brier)), 4),
                "test_accuracy": t_acc,
                "test_roc_auc": t_auc,
                "test_log_loss": t_loss,
                "test_brier_score": t_brier,
                "train_time_seconds": round(elapsed, 2),
                "is_best": False,
            }
            benchmark_list.append(result_entry)

            if "Baseline" in name:
                self.baseline_lr = clf
                self.baseline_metrics = ModelMetrics(
                    model_name=name,
                    train_samples=len(train_df),
                    test_samples=len(test_df),
                    accuracy=t_acc,
                    roc_auc=t_auc,
                    log_loss=t_loss,
                    brier_score=t_brier,
                    trained_at=datetime.now(UTC).isoformat(),
                    cv_accuracy=f"{cv_acc_m*100:.2f}% ± {cv_acc_s*100:.2f}%",
                    cv_roc_auc=f"{cv_auc_m:.4f} ± {cv_auc_s:.4f}",
                )

        # Mark best model
        for b in benchmark_list:
            if b["name"] == best_model_name:
                b["is_best"] = True
                self.metrics = ModelMetrics(
                    model_name=b["name"],
                    train_samples=len(train_df),
                    test_samples=len(test_df),
                    accuracy=b["test_accuracy"],
                    roc_auc=b["test_roc_auc"],
                    log_loss=b["test_log_loss"],
                    brier_score=b["test_brier_score"],
                    trained_at=datetime.now(UTC).isoformat(),
                    cv_accuracy=b["cv_accuracy"],
                    cv_roc_auc=b["cv_roc_auc"],
                )

        self.model = best_model_obj
        self.benchmark_results = benchmark_list

        # Extract Feature Importances
        self._extract_feature_importances()

        self.save_model()

        lgbm_entry = next((b for b in benchmark_list if "LightGBM" in b["name"]), {})
        lr_entry = next((b for b in benchmark_list if "Logistic" in b["name"]), {})

        return {
            "status": "success",
            "samples": len(df),
            "best_model": best_model_name,
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "lgbm": {
                "accuracy": lgbm_entry.get("test_accuracy", 0.0),
                "roc_auc": lgbm_entry.get("test_roc_auc", 0.0),
                "log_loss": lgbm_entry.get("test_log_loss", 0.0),
                "brier_score": lgbm_entry.get("test_brier_score", 0.0),
            },
            "baseline_lr": {
                "accuracy": lr_entry.get("test_accuracy", 0.0),
                "roc_auc": lr_entry.get("test_roc_auc", 0.0),
                "log_loss": lr_entry.get("test_log_loss", 0.0),
                "brier_score": lr_entry.get("test_brier_score", 0.0),
            },
            "benchmark": benchmark_list,
            "feature_importances": self.feature_importances,
        }

    def _extract_feature_importances(self) -> None:
        """Extract top ally assets, enemy threats, and feature weights."""
        if not self.brawler_ids or not self.brawler_to_idx:
            return

        n_brawlers = len(self.brawler_ids)
        importances = np.zeros(len(self.brawler_ids) * 2 + len(self.mode_to_idx) + 1)

        # Pull importance weights from active model
        if hasattr(self.model, "feature_importances_"):
            raw_imp = self.model.feature_importances_
            if len(raw_imp) == len(importances):
                importances = raw_imp / (np.sum(raw_imp) + 1e-9)
        elif hasattr(self.model, "estimators_"):
            # Ensemble
            sub_imps = []
            for est in self.model.estimators_:
                if hasattr(est, "feature_importances_"):
                    sub_imps.append(est.feature_importances_)
            if sub_imps:
                avg_imp = np.mean(sub_imps, axis=0)
                importances = avg_imp / (np.sum(avg_imp) + 1e-9)
        elif self.baseline_lr and hasattr(self.baseline_lr, "coef_"):
            importances = np.abs(self.baseline_lr.coef_[0])

        ally_imps = importances[:n_brawlers]
        enemy_imps = importances[n_brawlers : n_brawlers * 2]
        power_imp = float(importances[-1])

        # Map to brawlers
        stats = self.meta_engine.compute_brawler_stats(min_picks=1)
        name_map = {s["brawler_id"]: s["brawler_name"] for s in stats}

        top_allies = []
        for idx in np.argsort(ally_imps)[::-1][:15]:
            b_id = self.brawler_ids[idx]
            top_allies.append({
                "brawler_id": b_id,
                "brawler_name": name_map.get(b_id, f"Brawler #{b_id}"),
                "importance_weight": round(float(ally_imps[idx]), 4),
            })

        top_enemies = []
        for idx in np.argsort(enemy_imps)[::-1][:15]:
            b_id = self.brawler_ids[idx]
            top_enemies.append({
                "brawler_id": b_id,
                "brawler_name": name_map.get(b_id, f"Brawler #{b_id}"),
                "importance_weight": round(float(enemy_imps[idx]), 4),
            })

        self.feature_importances = {
            "top_ally_influencers": top_allies,
            "top_enemy_threats": top_enemies,
            "power_differential_weight": round(power_imp, 4),
            "total_features": len(importances),
        }

    def predict_match(
        self,
        mode: str,
        map_name: str,
        team_brawlers: list[int],
        enemy_brawlers: list[int],
        power_diff: float = 0.0,
    ) -> dict[str, Any]:
        """Predict win probability for complete or partial draft compositions."""
        if self.model is None or not self.brawler_to_idx:
            # Fallback to statistical prior
            return {
                "win_probability": 0.50,
                "confidence": "LOW",
                "source": "statistical_fallback",
                "model_version": "none",
            }

        # Build feature vector for single match
        n_brawlers = len(self.brawler_ids)
        n_modes = len(self.mode_to_idx)
        x = np.zeros((1, (n_brawlers * 2) + n_modes + 1), dtype=np.float32)

        for b in team_brawlers:
            if b in self.brawler_to_idx:
                x[0, self.brawler_to_idx[b]] = 1.0

        for b in enemy_brawlers:
            if b in self.brawler_to_idx:
                x[0, n_brawlers + self.brawler_to_idx[b]] = 1.0

        m_idx = self.mode_to_idx.get(mode)
        if m_idx is not None:
            x[0, (n_brawlers * 2) + m_idx] = 1.0

        x[0, -1] = float(power_diff)

        prob = float(self.model.predict_proba(x)[0, 1])

        # Confidence based on brawlers known in training pool
        known_team = sum(1 for b in team_brawlers if b in self.brawler_to_idx)
        known_enemy = sum(1 for b in enemy_brawlers if b in self.brawler_to_idx)
        total_picks = len(team_brawlers) + len(enemy_brawlers)
        known_picks = known_team + known_enemy
        
        confidence = "HIGH" if (known_picks >= 4 and total_picks >= 4) else ("MEDIUM" if total_picks >= 2 else "LOW")

        return {
            "win_probability": round(prob, 4),
            "confidence": confidence,
            "source": "lgbm_model",
            "model_version": self.version,
        }

    def recommend_brawlers(
        self,
        mode: str,
        map_name: Optional[str] = None,
        team_brawlers: Optional[list[int]] = None,
        enemy_brawlers: Optional[list[int]] = None,
        owned_brawlers: Optional[list[int]] = None,
        top_k: int = 15,
    ) -> list[dict[str, Any]]:
        """Rank remaining brawlers considering draft synergies, counters, and meta strength."""
        team = team_brawlers or []
        enemies = enemy_brawlers or []
        already_picked = set(team + enemies)

        # 1. Fetch statistical baseline for map/mode
        meta_stats = self.meta_engine.compute_brawler_stats(mode=mode, map_name=map_name)
        stats_by_id = {s["brawler_id"]: s for s in meta_stats}

        # Candidate pool: all known brawlers not yet picked
        candidates = [b_id for b_id in self.brawler_ids if b_id not in already_picked]
        if owned_brawlers is not None:
            owned_set = set(owned_brawlers)
            candidates = [b for b in candidates if b in owned_set]

        recommendations = []
        for cand_id in candidates:
            cand_stat = stats_by_id.get(cand_id)
            brawler_name = cand_stat["brawler_name"] if cand_stat else f"Brawler #{cand_id}"
            smoothed_wr = cand_stat["smoothed_win_rate"] if cand_stat else 0.50
            pick_rate = cand_stat["pick_rate"] if cand_stat else 0.01
            sample_count = cand_stat["total_picks"] if cand_stat else 0

            # 2. Evaluate simulated draft with ML model
            simulated_team = team + [cand_id]
            ml_pred = self.predict_match(
                mode=mode,
                map_name=map_name or "Unknown Map",
                team_brawlers=simulated_team,
                enemy_brawlers=enemies,
            )
            ml_win_prob = ml_pred["win_probability"]

            # 3. Compute synergy score with known teammates
            synergy_delta = 0.0
            synergy_reasons = []
            for ally_id in team:
                syn = self.meta_engine.compute_pair_synergy(cand_id, ally_id, mode=mode)
                if syn["paired_matches"] >= 3:
                    diff = syn["smoothed_win_rate"] - 0.50
                    synergy_delta += diff
                    if diff > 0.04:
                        synergy_reasons.append(f"High synergy with teammate (+{round(diff*100, 1)}% WR)")

            # 4. Compute counter score against known enemies
            counter_delta = 0.0
            counter_reasons = []
            for enemy_id in enemies:
                h2h = self.meta_engine.compute_head_to_head_counter(cand_id, enemy_id, mode=mode)
                if h2h["matches_faced"] >= 3:
                    diff = h2h["smoothed_win_rate"] - 0.50
                    counter_delta += diff
                    if diff > 0.05:
                        counter_reasons.append(f"Strong counter against opponent (+{round(diff*100, 1)}% WR)")

            # Composite recommendation score (0 - 100 scale)
            # Blends ML probability (45%), smoothed map win rate (35%), synergy (10%), and counter (10%)
            comp_score = (
                (ml_win_prob * 45.0)
                + (smoothed_wr * 35.0)
                + (np.clip(0.50 + synergy_delta, 0.3, 0.7) * 10.0)
                + (np.clip(0.50 + counter_delta, 0.3, 0.7) * 10.0)
            )

            # Build readable explanation
            reasons = []
            if cand_stat and cand_stat["tier"] in ("S", "A"):
                reasons.append(f"{cand_stat['tier']}-Tier in current meta ({round(cand_stat['smoothed_win_rate']*100, 1)}% WR)")
            reasons.extend(counter_reasons[:1])
            reasons.extend(synergy_reasons[:1])
            if not reasons:
                reasons.append(f"Reliable pick with {sample_count} tracked matches")

            recommendations.append({
                "brawler_id": cand_id,
                "brawler_name": brawler_name,
                "score": round(float(comp_score), 1),
                "estimated_win_probability": round(float(ml_win_prob), 4),
                "smoothed_win_rate": round(float(smoothed_wr), 4),
                "pick_rate": round(float(pick_rate), 4),
                "sample_count": sample_count,
                "tier": cand_stat["tier"] if cand_stat else "B",
                "confidence": ml_pred["confidence"],
                "explanation": " • ".join(reasons),
                "model_version": self.version,
            })

        recommendations.sort(key=lambda r: r["score"], reverse=True)
        return recommendations[:top_k]

    def evaluate_draft_step(
        self,
        mode: str,
        map_name: str,
        draft_allies: list[int],
        draft_enemies: list[int],
        active_slot: str = "ally_1",
        owned_brawlers: Optional[list[int]] = None,
        top_k: int = 12,
    ) -> dict[str, Any]:
        """Evaluate next pick options for active slot with projected win % deltas and synergy."""
        already_picked = set(draft_allies + draft_enemies)
        meta_stats = self.meta_engine.compute_brawler_stats(mode=mode, map_name=map_name)
        stats_by_id = {s["brawler_id"]: s for s in meta_stats}

        candidates = [b for b in self.brawler_ids if b not in already_picked]
        if owned_brawlers is not None:
            owned_set = set(owned_brawlers)
            candidates = [b for b in candidates if b in owned_set]

        # Base win probability with current locked picks
        base_pred = self.predict_match(mode=mode, map_name=map_name, team_brawlers=draft_allies, enemy_brawlers=draft_enemies)
        base_win_prob = base_pred["win_probability"]

        is_ally_slot = active_slot.startswith("ally")
        recommendations = []

        for cand_id in candidates:
            cand_stat = stats_by_id.get(cand_id)
            brawler_name = cand_stat["brawler_name"] if cand_stat else f"Brawler #{cand_id}"
            smoothed_wr = cand_stat["smoothed_win_rate"] if cand_stat else 0.50

            if is_ally_slot:
                sim_allies = draft_allies + [cand_id]
                sim_enemies = draft_enemies
            else:
                sim_allies = draft_allies
                sim_enemies = draft_enemies + [cand_id]

            sim_pred = self.predict_match(mode=mode, map_name=map_name, team_brawlers=sim_allies, enemy_brawlers=sim_enemies)
            new_win_prob = sim_pred["win_probability"]
            win_delta = (new_win_prob - base_win_prob) if is_ally_slot else (base_win_prob - new_win_prob)

            # Synergy with allies
            synergy_delta = 0.0
            reference_team = draft_allies if is_ally_slot else draft_enemies
            for teammate_id in reference_team:
                syn = self.meta_engine.compute_pair_synergy(cand_id, teammate_id, mode=mode, map_name=map_name)
                if syn["paired_matches"] >= 3:
                    synergy_delta += (syn["smoothed_win_rate"] - 0.50)

            # Counter against opponents
            counter_delta = 0.0
            opponents = draft_enemies if is_ally_slot else draft_allies
            for opp_id in opponents:
                h2h = self.meta_engine.compute_head_to_head_counter(cand_id, opp_id, mode=mode)
                if h2h["matches_faced"] >= 3:
                    counter_delta += (h2h["smoothed_win_rate"] - 0.50)

            # Composite score (0 - 100)
            score = (
                (new_win_prob * 45.0 if is_ally_slot else (1.0 - new_win_prob) * 45.0)
                + (smoothed_wr * 35.0)
                + (np.clip(0.50 + synergy_delta, 0.3, 0.7) * 10.0)
                + (np.clip(0.50 + counter_delta, 0.3, 0.7) * 10.0)
            )

            reason = []
            if cand_stat and cand_stat["tier"] in ("S", "A"):
                reason.append(f"{cand_stat['tier']}-Tier Meta ({round(smoothed_wr*100, 1)}% WR)")
            if win_delta > 0.02:
                reason.append(f"+{round(win_delta*100, 1)}% win delta")
            elif win_delta < -0.02:
                reason.append(f"{round(win_delta*100, 1)}% delta risk")
            if synergy_delta > 0.03:
                reason.append("High teammate synergy")
            if counter_delta > 0.04:
                reason.append("Counters active opponent")

            recommendations.append({
                "brawler_id": cand_id,
                "brawler_name": brawler_name,
                "projected_win_probability": round(new_win_prob, 4),
                "win_probability_delta": round(win_delta, 4),
                "win_rate_delta": round(win_delta, 4),
                "recommendation_score": round(score, 1),
                "score": round(score, 1),
                "smoothed_win_rate": round(smoothed_wr, 4),
                "synergy_score": round(synergy_delta, 3),
                "counter_score": round(counter_delta, 3),
                "explanation": " • ".join(reason[:2]) or "Balanced tactical pick",
                "rationale": " • ".join(reason[:2]) or "Balanced tactical pick",
                "tier": cand_stat["tier"] if cand_stat else "B",
                "sample_size": cand_stat["total_picks"] if cand_stat else 0,
            })

        recommendations.sort(key=lambda r: (r["recommendation_score"], r["projected_win_probability"]), reverse=True)

        return {
            "mode": mode,
            "map": map_name,
            "active_slot": active_slot,
            "current_allies": draft_allies,
            "current_enemies": draft_enemies,
            "base_win_probability": round(base_win_prob, 4),
            "current_win_probability": round(base_win_prob, 4),
            "recommendations": recommendations[:top_k],
            "candidates": recommendations[:top_k],
        }

    def save_model(self) -> None:
        model_path = self.model_dir / f"{self.version}.pkl"
        metadata_path = self.model_dir / f"{self.version}_meta.json"
        benchmark_path = self.model_dir / "model_benchmark.json"

        with model_path.open("wb") as f:
            pickle.dump({
                "model": self.model,
                "baseline_lr": self.baseline_lr,
                "brawler_ids": self.brawler_ids,
                "brawler_to_idx": self.brawler_to_idx,
                "mode_to_idx": self.mode_to_idx,
                "benchmark_results": self.benchmark_results,
                "feature_importances": self.feature_importances,
            }, f)

        meta_dict = {
            "version": self.version,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "baseline": self.baseline_metrics.to_dict() if self.baseline_metrics else None,
            "benchmark_summary": self.benchmark_results,
            "feature_importances": self.feature_importances,
        }
        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)

        if self.benchmark_results:
            with benchmark_path.open("w", encoding="utf-8") as f:
                json.dump({
                    "benchmarked_at": datetime.now(UTC).isoformat(),
                    "total_frameworks": len(self.benchmark_results),
                    "best_model": self.metrics.model_name if self.metrics else "Unknown",
                    "results": self.benchmark_results,
                    "feature_importances": self.feature_importances,
                }, f, indent=2)

        logger.info("Saved trained model and benchmark to %s", model_path)

    def load_model(self) -> bool:
        model_path = self.model_dir / f"{self.version}.pkl"
        metadata_path = self.model_dir / f"{self.version}_meta.json"

        # Fallback to lgbm_v1 if v2 does not exist yet
        if not model_path.exists():
            v1_path = self.model_dir / "lgbm_v1.pkl"
            if v1_path.exists():
                model_path = v1_path
                metadata_path = self.model_dir / "lgbm_v1_meta.json"
            else:
                return False

        try:
            with model_path.open("rb") as f:
                data = pickle.load(f)
            self.model = data.get("model")
            self.baseline_lr = data.get("baseline_lr")
            self.brawler_ids = data.get("brawler_ids", [])
            self.brawler_to_idx = data.get("brawler_to_idx", {})
            self.mode_to_idx = data.get("mode_to_idx", {})
            self.benchmark_results = data.get("benchmark_results", [])
            self.feature_importances = data.get("feature_importances", {})

            if metadata_path.exists():
                with metadata_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                    if meta.get("metrics"):
                        self.metrics = ModelMetrics(**meta["metrics"])
                    if meta.get("baseline"):
                        self.baseline_metrics = ModelMetrics(**meta["baseline"])
                    if meta.get("benchmark_summary"):
                        self.benchmark_results = meta["benchmark_summary"]
                    if meta.get("feature_importances"):
                        self.feature_importances = meta["feature_importances"]

            logger.info("Loaded model %s successfully", self.version)
            return True
        except Exception as exc:
            logger.error("Failed loading model %s: %s", self.version, exc)
            return False

