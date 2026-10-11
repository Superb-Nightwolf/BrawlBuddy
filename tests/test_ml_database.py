import tempfile
from pathlib import Path
import pytest

from app.ml.database import MetaDatabase, generate_match_fingerprint


def test_fingerprint_order_invariance():
    fp1 = generate_match_fingerprint(
        battle_time="20261011T120000.000Z",
        event_map="Center Stage",
        mode="brawlBall",
        participant_tags=["#TAG1", "#TAG2", "#TAG3"],
    )
    fp2 = generate_match_fingerprint(
        battle_time="20261011T120000.000Z",
        event_map="center stage",
        mode="BRAWLBALL",
        participant_tags=["#TAG3", "#TAG1", "#TAG2"],
    )
    assert fp1 == fp2
    assert len(fp1) == 24


def test_fingerprint_distinctness():
    fp1 = generate_match_fingerprint(
        battle_time="20261011T120000.000Z",
        event_map="Center Stage",
        mode="brawlBall",
        participant_tags=["#TAG1", "#TAG2"],
    )
    fp2 = generate_match_fingerprint(
        battle_time="20261011T120500.000Z",
        event_map="Center Stage",
        mode="brawlBall",
        participant_tags=["#TAG1", "#TAG2"],
    )
    assert fp1 != fp2


def test_database_initialization_and_player_ops():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_meta.db"
        db = MetaDatabase(db_path)

        assert db.get_player_count() == 0
        assert db.get_match_count() == 0

        # Save player
        saved = db.save_player(tag="#TEST123", name="Champion", trophies=1500, source="leaderboard", priority=3)
        assert saved is True
        assert db.get_player_count() == 1

        # Save again (update)
        db.save_player(tag="#test123", name="Champion", trophies=1600, source="leaderboard", priority=3)
        assert db.get_player_count() == 1

        unpolled = db.get_unpolled_players(limit=10)
        assert len(unpolled) == 1
        assert unpolled[0]["tag"] == "#TEST123"
        assert unpolled[0]["trophies"] == 1600

        # Mark polled
        db.mark_player_polled("#TEST123", battles_found=15)
        from contextlib import closing
        with closing(db.connect()) as conn:
            row = conn.execute("SELECT * FROM players WHERE tag = '#TEST123'").fetchone()
            assert row["battle_count"] == 15
            assert row["last_polled_at"] is not None


def test_match_deduplication():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_meta.db"
        db = MetaDatabase(db_path)

        mock_battle = {
            "battleTime": "20261011T140000.000Z",
            "event": {
                "id": 15000001,
                "mode": "gemGrab",
                "map": "Hard Rock Mine",
            },
            "battle": {
                "mode": "gemGrab",
                "type": "ranked",
                "result": "victory",
                "duration": 120,
                "teams": [
                    [
                        {"tag": "#P1", "name": "Player 1", "brawler": {"id": 16000000, "name": "SHELLY", "power": 11, "trophies": 800}},
                        {"tag": "#P2", "name": "Player 2", "brawler": {"id": 16000001, "name": "COLT", "power": 11, "trophies": 820}},
                        {"tag": "#P3", "name": "Player 3", "brawler": {"id": 16000002, "name": "BULL", "power": 10, "trophies": 790}},
                    ],
                    [
                        {"tag": "#P4", "name": "Player 4", "brawler": {"id": 16000003, "name": "BROCK", "power": 11, "trophies": 810}},
                        {"tag": "#P5", "name": "Player 5", "brawler": {"id": 16000004, "name": "RICO", "power": 11, "trophies": 805}},
                        {"tag": "#P6", "name": "Player 6", "brawler": {"id": 16000005, "name": "SPIKE", "power": 11, "trophies": 830}},
                    ],
                ],
            },
        }

        # First ingestion (from perspective of #P1)
        is_new, fp, discovered = db.save_match(mock_battle, source_player_tag="#P1")
        assert is_new is True
        assert db.get_match_count() == 1
        assert len(discovered) == 6

        from contextlib import closing
        with closing(db.connect()) as conn:
            parts = conn.execute("SELECT * FROM match_participants WHERE match_fingerprint = ?", (fp,)).fetchall()
            assert len(parts) == 6
            # Team 0 won since source was #P1 and result was 'victory'
            p1_row = [p for p in parts if p["player_tag"] == "#P1"][0]
            assert p1_row["is_winner"] == 1
            p4_row = [p for p in parts if p["player_tag"] == "#P4"][0]
            assert p4_row["is_winner"] == 0

        # Second ingestion (from perspective of #P4, who lost)
        mock_battle_from_p4 = dict(mock_battle)
        mock_battle_from_p4["battle"] = dict(mock_battle["battle"])
        mock_battle_from_p4["battle"]["result"] = "defeat"
        
        is_new_again, fp_again, _ = db.save_match(mock_battle_from_p4, source_player_tag="#P4")
        assert is_new_again is False  # Must be deduplicated!
        assert fp_again == fp
        assert db.get_match_count() == 1  # Still exactly 1 match!
