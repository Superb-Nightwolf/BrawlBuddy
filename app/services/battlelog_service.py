import json
import logging
from pathlib import Path
from typing import Any, Optional

from app.clients.brawl_stars import BrawlStarsClient
from app.models.battlelog import BattleBrawler, BattleEvent, BattleLogEntry, BattlePlayer

logger = logging.getLogger("brawlbuddy.battlelog_service")


class BattleLogService:
    def __init__(self, client: BrawlStarsClient, demo_path: Optional[Path] = None) -> None:
        self.client = client
        self.demo_path = demo_path or Path(__file__).resolve().parent.parent.parent / "data" / "demo_battlelog.json"
        self._cache: dict[str, list[BattleLogEntry]] = {}

    def parse_entry(self, raw: dict[str, Any]) -> BattleLogEntry:
        event_raw = raw.get("event", {})
        event = BattleEvent(
            id=event_raw.get("id", 0),
            mode=event_raw.get("mode", raw.get("battle", {}).get("mode", "brawlBall")),
            map=event_raw.get("map", "Unknown Map")
        )

        battle = raw.get("battle", {})
        mode = battle.get("mode", event.mode)
        result = battle.get("result")
        duration = battle.get("duration")
        trophy_change = battle.get("trophyChange")
        rank = battle.get("rank")

        # Star Player
        star_player_data = battle.get("starPlayer")
        star_player: Optional[BattlePlayer] = None
        if star_player_data:
            sp_brawler = star_player_data.get("brawler", {})
            star_player = BattlePlayer(
                tag=star_player_data.get("tag", ""),
                name=star_player_data.get("name", "Unknown"),
                brawler=BattleBrawler(
                    id=sp_brawler.get("id", 0),
                    name=sp_brawler.get("name", "Brawler"),
                    power=sp_brawler.get("power", 1),
                    trophies=sp_brawler.get("trophies", 0)
                ),
                is_star_player=True
            )

        # Teams
        teams: list[list[BattlePlayer]] = []
        for team_raw in battle.get("teams", []):
            team_players: list[BattlePlayer] = []
            for p in team_raw:
                pb = p.get("brawler", {})
                is_sp = star_player is not None and p.get("tag") == star_player.tag
                team_players.append(
                    BattlePlayer(
                        tag=p.get("tag", ""),
                        name=p.get("name", "Player"),
                        brawler=BattleBrawler(
                            id=pb.get("id", 0),
                            name=pb.get("name", "Brawler"),
                            power=pb.get("power", 1),
                            trophies=pb.get("trophies", 0)
                        ),
                        is_star_player=is_sp
                    )
                )
            teams.append(team_players)

        # Showdown solo/duo players
        players: list[BattlePlayer] = []
        for p in battle.get("players", []):
            pb = p.get("brawler", {})
            players.append(
                BattlePlayer(
                    tag=p.get("tag", ""),
                    name=p.get("name", "Player"),
                    brawler=BattleBrawler(
                        id=pb.get("id", 0),
                        name=pb.get("name", "Brawler"),
                        power=pb.get("power", 1),
                        trophies=pb.get("trophies", 0)
                    )
                )
            )

        # Power calculations
        team_a_avg = 0.0
        team_b_avg = 0.0
        if len(teams) >= 2 and len(teams[0]) > 0 and len(teams[1]) > 0:
            team_a_avg = round(sum(p.brawler.power for p in teams[0]) / len(teams[0]), 1)
            team_b_avg = round(sum(p.brawler.power for p in teams[1]) / len(teams[1]), 1)

        diff = team_a_avg - team_b_avg
        advantage = "blue_favored" if diff >= 0.5 else ("red_favored" if diff <= -0.5 else "balanced")

        return BattleLogEntry(
            battle_time=raw.get("battleTime", ""),
            event=event,
            mode=mode,
            type=battle.get("type", "ranked"),
            result=result,
            duration=duration,
            trophy_change=trophy_change,
            star_player=star_player,
            teams=teams,
            players=players,
            rank=rank,
            team_a_avg_power=team_a_avg,
            team_b_avg_power=team_b_avg,
            power_advantage=advantage
        )

    def load_demo(self) -> list[BattleLogEntry]:
        if not self.demo_path.exists():
            return []
        with self.demo_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [self.parse_entry(item) for item in data.get("items", [])]

    async def get_battlelog(self, player_tag: str) -> tuple[list[BattleLogEntry], str]:
        tag = player_tag.strip().upper()
        if not tag.startswith("#"):
            tag = f"#{tag}"

        if tag in self._cache:
            return self._cache[tag], "CACHE"

        if not self.client.api_key:
            demo_items = self.load_demo()
            return demo_items, "DEMO"

        try:
            raw_data = await self.client.get_battlelog(tag)
            items = [self.parse_entry(item) for item in raw_data.get("items", [])]
            self._cache[tag] = items
            return items, "LIVE"
        except Exception as e:
            logger.warning(f"Failed to fetch live battle log for {tag}: {e}. Falling back to demo.")
            return self.load_demo(), "DEMO"
