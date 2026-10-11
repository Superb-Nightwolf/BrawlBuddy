import pytest
from app.core.config import PROJECT_ROOT
from app.ml.database import MetaDatabase
from app.ml.meta_engine import StatisticalMetaEngine
from app.ml.model import BrawlerOutcomePredictor


def test_statistical_meta_engine():
    db_path = PROJECT_ROOT / "data" / "brawl_meta.db"
    assert db_path.exists(), "Meta DB should exist"
    db = MetaDatabase(db_path)
    engine = StatisticalMetaEngine(db)

    # Available filters
    filters = engine.get_available_filters()
    assert "modes" in filters
    assert len(filters["modes"]) > 0
    assert "brawlBall" in filters["modes"]

    # Brawler stats for brawlBall
    stats = engine.compute_brawler_stats(mode="brawlBall", min_picks=1)
    assert len(stats) > 0
    first = stats[0]
    assert "brawler_id" in first
    assert "smoothed_win_rate" in first
    assert "tier" in first
    assert first["tier"] in ("S", "A", "B", "C", "D")
    assert 0.0 <= first["smoothed_win_rate"] <= 1.0


def test_brawler_outcome_predictor_loading_and_prediction():
    db_path = PROJECT_ROOT / "data" / "brawl_meta.db"
    db = MetaDatabase(db_path)
    predictor = BrawlerOutcomePredictor(db)

    loaded = predictor.load_model()
    assert loaded is True, "Trained model should be loadable"
    assert predictor.metrics is not None
    assert predictor.metrics.roc_auc > 0.80

    # Test prediction
    pred = predictor.predict_match(
        mode="brawlBall",
        map_name="Center Stage",
        team_brawlers=[16000000, 16000001, 16000002],  # Shelly, Colt, Bull
        enemy_brawlers=[16000003, 16000004, 16000005],  # Brock, Rico, Spike
    )
    assert "win_probability" in pred
    assert 0.0 <= pred["win_probability"] <= 1.0
    assert pred["source"] == "lgbm_model"


def test_recommend_brawlers():
    db_path = PROJECT_ROOT / "data" / "brawl_meta.db"
    db = MetaDatabase(db_path)
    predictor = BrawlerOutcomePredictor(db)
    predictor.load_model()

    recs = predictor.recommend_brawlers(
        mode="brawlBall",
        team_brawlers=[16000000],  # Shelly selected
        enemy_brawlers=[16000003], # Brock on enemy
        top_k=5,
    )
    assert len(recs) == 5
    for r in recs:
        assert "brawler_id" in r
        assert "score" in r
        assert "explanation" in r
        assert r["brawler_id"] not in (16000000, 16000003)  # Already picked
