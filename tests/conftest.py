import pytest


@pytest.fixture
def ml_store(tmp_path):
    from datetime import datetime, timedelta
    from app.ml.database import MetaDatabase
    import random
    database = MetaDatabase(tmp_path / 'meta.db')
    rng = random.Random(9)
    for index in range(40):
        ids = rng.sample(range(16000000, 16000008), 6)
        teams = [[{'tag': f'#P{side*3 + slot+1}', 'name': 'Player',
                   'brawler': {'id': ids[side*3+slot], 'name': f'BRAWLER {ids[side*3+slot]}',
                               'power': 11, 'trophies': 800}} for slot in range(3)] for side in range(2)]
        battle = {'battleTime': (datetime(2026, 10, 10) + timedelta(minutes=index)).strftime('%Y%m%dT%H%M%S.000Z'),
                  'event': {'mode': 'brawlBall', 'map': 'Center Stage'},
                  'battle': {'mode': 'brawlBall', 'type': 'ranked',
                             'result': 'victory' if index % 2 else 'defeat', 'teams': teams}}
        database.save_match(battle, '#P1')
    return database
