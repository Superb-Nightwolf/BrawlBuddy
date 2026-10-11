from contextlib import closing
import pytest
from app.ml.collector import BattleLogCollector
from app.core.errors import ApiAuthenticationError


@pytest.mark.asyncio
async def test_discovery_stops_on_auth_failure(ml_store):
    class Unauthorized:
        calls=0
        async def get_rankings_players(self, region):
            self.calls+=1
            raise ApiAuthenticationError('Not authorized')
    client=Unauthorized()
    collector=BattleLogCollector(client,ml_store)
    with pytest.raises(ApiAuthenticationError):
        await collector.discover_top_players(target_player_count=100,regions=['global','us'],include_clubs=False,include_brawlers=False)
    assert client.calls==1


def test_oldest_polled_player_is_not_starved_by_priority(ml_store):
    ml_store.save_player('#LOW','Low priority',priority=1)
    ml_store.save_player('#HIGH','High priority',priority=3)
    with closing(ml_store.connect()) as conn,conn:
        conn.execute("UPDATE players SET last_polled_at='2026-10-11T01:00:00' WHERE tag='#LOW'")
        conn.execute("UPDATE players SET last_polled_at='2026-10-12T01:00:00' WHERE tag='#HIGH'")
    assert ml_store.get_unpolled_players(limit=2)[0]['tag']=='#LOW'


@pytest.mark.asyncio
async def test_malformed_entry_does_not_repeat_the_whole_player_poll(ml_store):
    ml_store.save_player('#P1','Player')
    class Client:
        async def get_battlelog(self,tag):
            return {'items': [
                {'battleTime':'broken'},
                {'battleTime':'20261012T070000.000Z','event':{'map':'Center Stage'},
                 'battle':{'mode':'brawlBall','result':'victory','teams':[
                    [{'tag':'#P1','brawler':{'id':16000000,'power':11}}],
                    [{'tag':'#P2','brawler':{'id':16000001,'power':11}}]]}},
            ]}
    stats=await BattleLogCollector(Client(),ml_store).collect_battlelogs(max_players=1)
    assert stats.malformed_entries_skipped==1
    assert stats.players_polled==1
    assert stats.new_matches_saved==1
