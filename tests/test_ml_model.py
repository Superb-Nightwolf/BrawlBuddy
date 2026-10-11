from contextlib import closing
from app.ml.meta_engine import StatisticalMetaEngine
from app.ml.model import BrawlerOutcomePredictor


def test_meta_stats_use_actual_slots_and_verified_labels(ml_store):
    engine = StatisticalMetaEngine(ml_store)
    stats = engine.compute_brawler_stats(mode='brawlBall')
    assert abs(sum(s['pick_rate'] for s in stats) - 1) < .001
    assert sum(s['wins'] for s in stats) == 120
    with closing(ml_store.connect()) as conn, conn:
        conn.execute('UPDATE matches SET ingestion_version=0')
    assert engine.compute_brawler_stats() == []


def test_fallback_has_no_invented_probability_or_confidence(ml_store):
    predictor = BrawlerOutcomePredictor(ml_store)
    pred = predictor.predict_match('brawlBall', 'Center Stage', [16000000], [])
    assert pred['source'] == 'statistical_fallback'
    assert pred['confidence'] == 'LOW'
    assert predictor.load_model() is False
    recs = predictor.recommend_brawlers('brawlBall', 'Center Stage', [16000000], [16000003], top_k=5)
    assert len(recs) == 5
    assert all(r['brawler_id'] not in {16000000, 16000003} for r in recs)
    assert all(r['model_version'] == 'none' for r in recs)


def test_training_uses_temporal_holdout_and_persists_map_features(ml_store, monkeypatch):
    import app.ml.model as module
    monkeypatch.setattr(module, 'lgb', None)
    monkeypatch.setattr(module, 'xgb', None)
    predictor = BrawlerOutcomePredictor(ml_store)
    result = predictor.train_and_evaluate(n_splits=3)
    assert result['status'] == 'success'
    validation = result['validation']
    assert validation['train_latest'] < validation['test_earliest']
    assert validation['train_matches'] + validation['test_matches'] == 40
    assert result['metrics']['train_samples'] == validation['train_matches'] * 2
    champion = next(row for row in result['benchmark'] if row['is_best'])
    assert champion['cv_log_loss_mean'] == min(row['cv_log_loss_mean'] for row in result['benchmark'])
    loaded = BrawlerOutcomePredictor(ml_store)
    assert loaded.load_model()
    assert loaded.map_to_idx == predictor.map_to_idx
    team, enemy = [16000000, 16000001, 16000002], [16000003, 16000004, 16000005]
    a = loaded.predict_match('brawlBall', 'Center Stage', team, enemy)
    b = loaded.predict_match('brawlBall', 'Center Stage', enemy, team)
    assert abs(a['win_probability'] + b['win_probability'] - 1) < .0002
    assert a['source'] == 'outcome_model'
    unknown = loaded.predict_match('brawlBall', 'Unseen Map', team, enemy)
    assert unknown['source'] == 'statistical_fallback'


def test_unverified_legacy_rows_do_not_train(ml_store):
    with closing(ml_store.connect()) as conn, conn:
        conn.execute('UPDATE matches SET ingestion_version=0')
    result = BrawlerOutcomePredictor(ml_store).train_and_evaluate()
    assert result['status'] == 'insufficient_data'


def test_draft_loads_pair_evidence_once_and_keeps_map_scope(ml_store, monkeypatch):
    predictor = BrawlerOutcomePredictor(ml_store)
    original = predictor.meta_engine.compute_interactions
    calls=[]
    def interactions(mode, map_name):
        calls.append((mode, map_name))
        return original(mode,map_name)
    monkeypatch.setattr(predictor.meta_engine,'compute_interactions',interactions)
    recommendations=predictor.recommend_brawlers('brawlBall','Center Stage',[16000000],[16000001])
    assert recommendations
    assert calls==[('brawlBall','Center Stage')]
    assert predictor.recommend_brawlers('brawlBall','Unseen Map')==[]
