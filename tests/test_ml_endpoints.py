import asyncio
import threading
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.ml.meta_engine import StatisticalMetaEngine
from app.ml.model import BrawlerOutcomePredictor
from app.routers import ml_meta as routes


@pytest.fixture
def ml_client(ml_store, monkeypatch):
    monkeypatch.setattr(routes, 'meta_db', ml_store)
    monkeypatch.setattr(routes, 'meta_engine', StatisticalMetaEngine(ml_store))
    monkeypatch.setattr(routes, 'predictor', BrawlerOutcomePredictor(ml_store))
    monkeypatch.setattr(routes, 'operation_task', None)
    monkeypatch.setattr(routes, 'operation_state', {'running': False, 'task': 'Idle', 'message': '', 'last_result': None, 'progress': {}})
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize('url', ['/api/meta/filters', '/api/meta/brawlers?mode=brawlBall',
    '/api/meta/teams?mode=brawlBall&min_matches=1', '/api/ml/model-status',
    '/api/ml/transparency/summary', '/api/ml/operations/telemetry', '/api/ml/operations/status', '/meta'])
def test_ml_routes(ml_client, url):
    assert ml_client.get(url).status_code == 200


def test_bulk_progress_reports_fresh_external_worker(ml_client, monkeypatch, tmp_path):
    import json
    from datetime import UTC, datetime
    monkeypatch.setattr(routes, 'bulk_dataset_directory', tmp_path)
    (tmp_path / 'progress.json').write_text(json.dumps({'updated_at': datetime.now(UTC).isoformat(),
        'state': 'running', 'selected_players': 100000, 'unique_matches': 2000}))
    response = ml_client.get('/api/ml/bulk-dataset/status').json()
    assert response['available'] is True
    assert response['is_stale'] is False
    assert response['unique_matches'] == 2000
    assert response['selected_players'] == 100000


def test_bulk_progress_flags_stale_running_report(ml_client, monkeypatch, tmp_path):
    import json
    from datetime import UTC, datetime, timedelta
    monkeypatch.setattr(routes, 'bulk_dataset_directory', tmp_path)
    (tmp_path / 'progress.json').write_text(json.dumps({'updated_at': (datetime.now(UTC)-timedelta(minutes=5)).isoformat(), 'state': 'running'}))
    response = ml_client.get('/api/ml/bulk-dataset/status').json()
    assert response['is_stale'] is True


def test_bulk_progress_handles_missing_and_malformed_report(ml_client, monkeypatch, tmp_path):
    monkeypatch.setattr(routes, 'bulk_dataset_directory', tmp_path)
    assert ml_client.get('/api/ml/bulk-dataset/status').json()['state'] == 'not_started'
    (tmp_path / 'progress.json').write_text('{broken')
    assert ml_client.get('/api/ml/bulk-dataset/status').json()['state'] == 'unavailable'


@pytest.mark.parametrize('payload', [
    {'teamBrawlers': [16000000]*2},
    {'teamBrawlers': [16000000], 'enemyBrawlers': [16000000]},
    {'teamBrawlers': list(range(16000000, 16000004))},
    {'mode': 'soloShowdown'}, {'powerDiff': 99},
])
def test_invalid_drafts_are_rejected(ml_client, payload):
    assert ml_client.post('/api/ml/predict-match', json=payload).status_code == 422


def test_owned_collection_uses_player_service_tuple(ml_client, monkeypatch):
    from types import SimpleNamespace
    class PlayerService:
        async def get_player(self, tag):
            return SimpleNamespace(brawlers=[SimpleNamespace(id=16000000)]), 'CACHE'
    monkeypatch.setattr(app.state, 'player_service', PlayerService())
    response = ml_client.post('/api/ml/recommend', json={'ownedBrawlersOnly': True, 'playerTag': '#P1'})
    assert response.status_code == 200
    assert response.json()['ownedFiltered'] is True
    assert [r['brawler_id'] for r in response.json()['recommendations']] == [16000000]


def test_owned_filter_fails_visibly_instead_of_recommending_unowned(ml_client, monkeypatch):
    class BrokenService:
        async def get_player(self, tag):
            raise RuntimeError('offline')
    monkeypatch.setattr(app.state, 'player_service', BrokenService())
    response = ml_client.post('/api/ml/recommend', json={'ownedBrawlersOnly': True, 'playerTag': '#P1'})
    assert response.status_code == 502
    assert ml_client.post('/api/ml/recommend', json={'ownedBrawlersOnly': True}).status_code == 422


def test_training_runs_in_background_and_prevents_overlap(ml_client, monkeypatch):
    gate, entered = threading.Event(), threading.Event()
    def train(self):
        entered.set()
        gate.wait(3)
        return {'status': 'insufficient_data', 'message': 'More verified matches needed'}
    monkeypatch.setattr(BrawlerOutcomePredictor, 'train_and_evaluate', train)
    response = ml_client.post('/api/ml/operations/retrain')
    assert response.status_code == 202
    assert entered.wait(1)
    try:
        assert ml_client.get('/api/ml/operations/status').json()['running'] is True
        assert ml_client.post('/api/ml/operations/retrain').status_code == 409
        assert ml_client.get('/api/meta/brawlers').status_code == 200
    finally:
        gate.set()
