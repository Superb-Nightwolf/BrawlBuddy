from __future__ import annotations

import csv
import gzip
import json
from datetime import datetime, timedelta

import pytest

from app.core.errors import ApiAuthenticationError
from app.ml.bulk_dataset import BulkDataset, BulkDatasetWorker, dataset_lock


def battles(count=25, source='#P1', offset=0, result='victory'):
    teams = [[{'tag': f'#P{side * 3 + slot + 1}', 'name': 'Player',
               'brawler': {'id': 16000000 + side * 3 + slot, 'power': 11}}
              for slot in range(3)] for side in range(2)]
    return [{'battleTime': (datetime(2026, 10, 12) + timedelta(minutes=index + offset)).strftime('%Y%m%dT%H%M%S.000Z'),
             'event': {'mode': 'brawlBall', 'map': 'Center Stage'},
             'battle': {'mode': 'brawlBall', 'type': 'ranked', 'result': result, 'teams': teams}}
            for index in range(count)]


@pytest.fixture
def sample(tmp_path):
    dataset = BulkDataset(tmp_path, target_players=2, matches_per_player=50)
    dataset.add_players([{'tag': '#P1', 'name': 'One', 'trophies': 100000},
                         {'tag': '#P4', 'name': 'Four', 'trophies': 90000}], 'account_leaderboard', 'global', 3)
    dataset.freeze_cohort()
    yield dataset
    dataset.close()


def test_repeated_poll_does_not_count_towards_fifty(sample):
    assert sample.save_poll('#P1', battles(), 0, 12) == 25
    assert sample.save_poll('#P1', battles(), 0, 12) == 0
    summary = sample.summary()
    assert summary['unique_matches'] == summary['player_match_observations'] == 25
    assert summary['players_at_target'] == 0
    assert sample.save_poll('#P1', battles(40, offset=20), 0, 12) == 25
    assert sample.summary()['players_at_target'] == 1
    assert sample.summary()['player_match_observations'] == 50
    assert sample.save_poll('#P1', battles(offset=100), 0, 12) == 0


def test_shared_matches_keep_source_relative_results_separate(sample):
    sample.save_poll('#P1', battles(1), 0, 12)
    sample.save_poll('#P4', battles(1, result='defeat'), 0, 12)
    assert sample.summary()['unique_matches'] == 1
    assert sample.summary()['player_match_observations'] == 2
    sample.export_csv()
    with gzip.open(sample.directory / 'matches.csv.gz', 'rt', encoding='utf-8', newline='') as handle:
        match = list(csv.DictReader(handle))[0]
    with gzip.open(sample.directory / 'player_matches.csv.gz', 'rt', encoding='utf-8', newline='') as handle:
        observations = list(csv.DictReader(handle))
    assert match['first_source_tag'] == '#P1'
    assert json.loads(match['raw_json'])['battle']['result'] == 'victory'
    assert {row['player_tag']: row['result'] for row in observations} == {'#P1': 'victory', '#P4': 'defeat'}


def test_missing_source_and_invalid_time_not_counted(sample):
    item = battles(1)[0]
    item['battleTime'] = 'invalid'
    assert sample.save_poll('#P1', [item], 0, 12) == 0
    item = battles(1)[0]
    item['battle']['teams'][0][0]['tag'] = '#OTHER'
    assert sample.save_poll('#P1', [item], 0, 12) == 0
    assert sample.summary()['malformed_entries'] == 2
    assert sample.summary()['unique_matches'] == 0


def test_stalled_players_are_visible_and_not_complete(sample):
    sample.save_poll('#P1', [], 0, 2)
    sample.save_poll('#P1', [], 0, 2)
    assert sample.summary()['stalled_players'] == 1
    assert sample.summary()['players_at_target'] == 0


def test_friendly_or_missing_power_not_trainable(sample):
    friendly, missing = battles(2)
    friendly['battle']['type'] = 'friendly'
    missing['battle']['teams'][0][0]['brawler']['power'] = 0
    sample.save_poll('#P1', [friendly, missing], 0, 12)
    assert sample.summary()['unique_matches'] == 2
    assert sample.summary()['eligible_3v3_matches'] == 0


def test_resume_preserves_counts_and_cohort(tmp_path):
    dataset = BulkDataset(tmp_path, 1, 50)
    dataset.add_players([{'tag': '#P1'}], 'account_leaderboard')
    dataset.freeze_cohort()
    dataset.save_poll('#P1', battles(), 0, 12)
    dataset.close()
    resumed = BulkDataset(tmp_path, 1, 50)
    assert resumed.summary()['player_match_observations'] == 25
    assert resumed.summary()['selected_players'] == 1
    assert resumed.get('phase') == 'collection'
    resumed.close()
    with pytest.raises(ValueError, match='different targets'):
        BulkDataset(tmp_path, 1, 40)


def test_brawler_trophies_never_become_account_trophies(sample):
    sample.add_players([{'tag': '#P1', 'trophies': 200000}], 'brawler_leaderboard', priority=1, account_trophies=False)
    row = sample.conn.execute("SELECT * FROM players WHERE tag='#P1'").fetchone()
    assert row['trophies'] == 100000
    assert row['source'] == 'account_leaderboard'


def test_cohort_target_and_provenance(tmp_path):
    dataset = BulkDataset(tmp_path, 2, 50)
    dataset.add_players([{'tag': '#P1'}, {'tag': '#P2'}], 'account_leaderboard', 'global', 3)
    dataset.add_players([{'tag': '#P3', 'trophies': 1000000}], 'match_participant', priority=0)
    dataset.freeze_cohort()
    selected = [row[0] for row in dataset.conn.execute('SELECT tag FROM players WHERE cohort=1')]
    assert set(selected) == {'#P1', '#P2'}
    dataset.close()


def test_csv_handles_unicode_and_escapes_formulas(sample):
    sample.add_players([{'tag': '#P1', 'name': '=HYPERLINK("unsafe")'}, {'tag': '#P4', 'name': '天堂🍁'}], 'account_leaderboard')
    sample.export_csv()
    with (sample.directory / 'players.csv').open(encoding='utf-8', newline='') as handle:
        names = {row['tag']: row['name'] for row in csv.DictReader(handle)}
    assert names['#P1'].startswith("'=HYPERLINK")
    assert names['#P4'] == '天堂🍁'
    assert not list(sample.directory.glob('*.tmp'))


def test_worker_lock_prevents_duplicate_processes(tmp_path):
    with dataset_lock(tmp_path):
        with pytest.raises(OSError):
            with dataset_lock(tmp_path):
                pass
    with dataset_lock(tmp_path):
        pass


@pytest.mark.asyncio
async def test_worker_finishes_only_when_every_player_has_target(tmp_path):
    dataset = BulkDataset(tmp_path, 1, 50)
    class Client:
        polls = 0
        async def get_rankings_players(self, region):
            return {'items': [{'tag': '#P1', 'name': 'Player'}]}
        async def get_battlelog(self, tag):
            self.polls += 1
            return {'items': battles(offset=25 * (self.polls - 1))}
    worker = BulkDatasetWorker(Client(), dataset, rps=100000, poll_hours=0, regions=['global'])
    await worker.run()
    assert dataset.summary()['state'] == 'complete'
    assert dataset.summary()['players_at_target'] == 1
    assert dataset.summary()['player_match_observations'] == 50
    dataset.close()


@pytest.mark.asyncio
async def test_auth_failure_persists_resume_state_and_csv(tmp_path):
    dataset = BulkDataset(tmp_path, 2, 50)
    class Client:
        async def get_rankings_players(self, region):
            raise ApiAuthenticationError('Unauthorized')
    await BulkDatasetWorker(Client(), dataset, regions=['global']).run()
    assert dataset.summary()['state'] == 'needs_token'
    assert (tmp_path / 'players.csv').exists()
    assert dataset.conn.execute("SELECT status FROM tasks WHERE kind='players'").fetchone()[0] == 'pending'
    dataset.close()
