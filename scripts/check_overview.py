"""Local browser smoke checks and screenshots for the Overview dashboard."""
import asyncio
import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "overview-preview"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
sys.path.insert(0, str(ROOT))

from app.models.club import ClubProfile
from app.models.player import DataSource
from app.services.club_analytics_service import summarize_club_roster


async def main():
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brawlbuddy_overview_") as profile:
        process = subprocess.Popen([
            str(CHROME), "--headless=new", "--remote-debugging-port=0",
            f"--user-data-dir={profile}", "--disable-gpu", "--hide-scrollbars", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            port_file = Path(profile) / "DevToolsActivePort"
            for _ in range(60):
                if port_file.exists():
                    break
                await asyncio.sleep(.1)
            port = int(port_file.read_text().splitlines()[0])
            async with httpx.AsyncClient() as client:
                pages = (await client.get(f"http://127.0.0.1:{port}/json/list")).json()
            page = next(page for page in pages if page["type"] == "page")
            async with websockets.connect(page["webSocketDebuggerUrl"], max_size=32*1024*1024) as ws:
                sequence = 0
                errors = []

                async def send(method, params=None):
                    nonlocal sequence
                    sequence += 1
                    message_id = sequence
                    await ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
                    while True:
                        message = json.loads(await ws.recv())
                        if message.get("method") == "Runtime.exceptionThrown":
                            errors.append(message["params"]["exceptionDetails"])
                        if message.get("id") == message_id:
                            if "error" in message:
                                raise RuntimeError(message["error"])
                            return message.get("result", {})

                async def evaluate(expression, await_promise=False):
                    result = await send("Runtime.evaluate", {"expression": expression,
                                        "returnByValue": True, "awaitPromise": await_promise})
                    if "exceptionDetails" in result:
                        raise RuntimeError(result["exceptionDetails"])
                    return result.get("result", {}).get("value")

                async def ready():
                    for _ in range(180):
                        if await evaluate("document.querySelectorAll('#overview-dashboard .ov-card').length > 20 && document.querySelector('#overview-dashboard')?.getAttribute('aria-busy') === 'false'"):
                            return
                        await asyncio.sleep(.2)
                    failure = await send("Page.captureScreenshot", {"format": "png"})
                    (OUTPUT / "failure.png").write_bytes(base64.b64decode(failure["data"]))
                    raise RuntimeError(await evaluate("JSON.stringify({url:location.href,title:document.title,body:document.body?.innerText.slice(0,2000),dashboard:document.querySelector('#overview-dashboard')?.innerText,ready:document.readyState})"))

                async def screenshot(name, section=None):
                    if section:
                        await evaluate(f"document.getElementById('{section}').scrollIntoView({{behavior:'instant',block:'start'}})")
                    else:
                        await evaluate("window.scrollTo({top:0,behavior:'instant'})")
                    await asyncio.sleep(.25)
                    result = await send("Page.captureScreenshot", {"format": "png"})
                    (OUTPUT / name).write_bytes(base64.b64decode(result["data"]))

                async def club_ready():
                    for _ in range(180):
                        if await evaluate("state.club && document.querySelectorAll('#club-dashboard .ov-card').length === 13"):
                            return
                        await asyncio.sleep(.2)
                    raise RuntimeError(await evaluate("document.querySelector('#club-view').innerText"))

                await send("Page.enable")
                await send("Runtime.enable")
                await send("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1050,
                            "deviceScaleFactor": 1, "mobile": False})
                print("Navigation:", await send("Page.navigate", {"url": "http://127.0.0.1:8000/"}), flush=True)
                await ready()
                print("Desktop cards:", await evaluate("document.querySelectorAll('#overview-dashboard .ov-card').length"))
                assert not await evaluate("document.documentElement.scrollWidth > innerWidth"), "Desktop overflow"
                assert await evaluate("document.querySelectorAll('#overview-dashboard .ov-section-heading').length") == 7
                assert await evaluate("document.querySelectorAll('#overview-dashboard .ov-group').length") == 7
                assert await evaluate("document.querySelectorAll('.ov-group .ov-card').length") == 30
                await evaluate("document.querySelectorAll('#overview-dashboard img').forEach(img=>img.loading='eager');Promise.race([Promise.all([...document.querySelectorAll('#overview-dashboard img')].map(img=>img.decode().catch(()=>{}))),new Promise(resolve=>setTimeout(resolve,10000))])", True)
                assert not await evaluate("[...document.querySelectorAll('#overview-dashboard img')].filter(img=>!img.naturalWidth).map(img=>img.src)"), "Broken Overview artwork"
                assert not await evaluate("document.querySelector('#overview-view').innerText.includes('★')"), "Star character returned"
                assert await evaluate("document.querySelector('.ov-stat-pink .ov-stat-heading svg').classList.contains('ov-ui-symbol')"), "Power 11 still uses an equipment badge"
                assert not await evaluate("document.querySelector('.ov-stat-orange').innerHTML.includes('wipeout')"), "Win streak still uses a mode icon"
                assert not await evaluate("[...document.querySelectorAll('[id]')].map(e=>e.id).filter((v,i,a)=>a.indexOf(v)!==i).length"), "Duplicate IDs"
                await screenshot("desktop-top.png")
                for route, page_name, condition in (
                    ("/brawlers", "reference-roster.png", "document.querySelectorAll('#brawler-grid .brawler-card').length > 0"),
                    ("/brawlers/16000000", "reference-detail.png", "state.page === 'detail' && !document.querySelector('#detail-view').classList.contains('hidden')"),
                ):
                    await send("Page.navigate", {"url": "http://127.0.0.1:8000" + route})
                    for _ in range(120):
                        if await evaluate(condition):
                            break
                        await asyncio.sleep(.2)
                    await asyncio.sleep(.6)
                    await screenshot(page_name)
                await send("Page.navigate", {"url": "http://127.0.0.1:8000/"})
                await ready()
                await screenshot("desktop-collection.png", "ov-collection")
                await screenshot("desktop-equipment.png", "ov-equipment")
                await screenshot("desktop-ranked.png", "ov-competitive")
                await screenshot("desktop-recent.png", "ov-recent")
                await screenshot("desktop-goals.png", "ov-goals")
                await evaluate("document.querySelector('#ov-trophy-sort').value='highest_trophies';document.querySelector('#ov-trophy-sort').dispatchEvent(new Event('change',{bubbles:true}))")
                assert await evaluate("document.querySelectorAll('#ov-top-trophies .ov-bar-row').length") == 10
                await evaluate("document.querySelector('.ov-ledger').open=true;document.querySelector('#ov-roster-search').value='shelly';document.querySelector('#ov-roster-search').dispatchEvent(new Event('input',{bubbles:true}))")
                assert await evaluate("document.querySelectorAll('#ov-roster-table tbody tr').length") == 1
                await evaluate("document.querySelector('#ov-roster-search').value='';document.querySelector('#ov-roster-search').dispatchEvent(new Event('input',{bubbles:true}))")
                assert await evaluate("document.querySelectorAll('#ov-roster-table tbody tr').length") > 100
                await evaluate("document.querySelector('.ov-ledger').open=false")
                await evaluate("OverviewDashboard.load(true)", True)
                await ready()
                assert not await evaluate("document.querySelector('#overview-refresh').disabled")
                await send("Page.navigate", {"url": "http://127.0.0.1:8000/club/%232Q0UG28YJ"})
                await club_ready()
                assert await evaluate("state.club.tag") == "#2Q0UG28YJ", "Requested club route ignored"
                assert await evaluate("document.querySelector('#club-prestige-badge').innerText") == "CLUB SNAPSHOT", "Invented club tier"
                assert await evaluate("document.querySelectorAll('#club-members-tbody tr').length") == await evaluate("state.club.members.length")
                await evaluate("window.savedClubPayload={club:state.club,analytics:state.clubAnalytics,freshness:{cache_hit:true}}")
                await evaluate("document.querySelector('#club-target-input').value=state.clubAnalytics.roster_trophies+1000;document.querySelector('#club-target-input').dispatchEvent(new Event('change',{bubbles:true}))")
                assert await evaluate("document.querySelector('#club-target-plan .club-plan-values').innerText.includes('1,000')")
                await evaluate("document.querySelector('#roster-search').value=state.clubAnalytics.rows[0].tag;document.querySelector('#roster-search').dispatchEvent(new Event('input',{bubbles:true}))")
                assert await evaluate("document.querySelectorAll('#club-members-tbody tr').length") == 1
                await evaluate("document.querySelector('#roster-search').value='';document.querySelector('#roster-search').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#club-role-filter').value='president';document.querySelector('#club-role-filter').dispatchEvent(new Event('change',{bubbles:true}))")
                assert await evaluate("document.querySelectorAll('#club-members-tbody tr').length") == await evaluate("state.clubAnalytics.presidents_count")
                await evaluate("document.querySelector('#club-role-filter').value='all';document.querySelector('#club-role-filter').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#club-roster-sort').value='trophies_asc';document.querySelector('#club-roster-sort').dispatchEvent(new Event('change',{bubbles:true}))")
                assert await evaluate("Number(document.querySelector('#club-members-tbody tr:first-child .roster-trophies').innerText.replaceAll(',','')) <= Number(document.querySelector('#club-members-tbody tr:last-child .roster-trophies').innerText.replaceAll(',',''))")
                for width in (1440,768,390,360):
                    await send("Emulation.setDeviceMetricsOverride", {"width":width,"height":1050 if width==1440 else 900,"deviceScaleFactor":1,"mobile":width<640})
                    await asyncio.sleep(.3)
                    assert not await evaluate("document.documentElement.scrollWidth > innerWidth"), f"Club overflow at {width}"
                    assert not await evaluate("[...document.querySelectorAll('#club-dashboard .ov-stat')].filter(card=>card.scrollWidth>card.clientWidth+1).map(card=>card.innerText)"), f"Club metric overflow at {width}"
                    for name, section in (("top",None),("distribution","club-distribution"),("contributions","club-contributions"),("planning","club-planning"),("roster","roster")):
                        await screenshot(f"club-{width}-{name}.png",section)
                await evaluate("window.clubOriginalFetch=window.fetch;window.fetch=(url,options)=>String(url).includes('/api/club')?Promise.resolve(new Response(JSON.stringify({error:{message:'Temporary club failure'}}),{status:503,headers:{'Content-Type':'application/json'}})):clubOriginalFetch(url,options);ClubDashboard.refresh()",True)
                assert await evaluate("document.querySelector('#club-refresh-status').innerText.includes('Temporary club failure')")
                assert not await evaluate("document.querySelector('#club-refresh').disabled")
                assert await evaluate("document.querySelectorAll('#club-dashboard .ov-card').length") == 13
                await evaluate("window.fetch=window.clubOriginalFetch;ClubDashboard.refresh()",True)
                await club_ready()
                await evaluate("loadDemoClub()",True)
                await club_ready()
                assert await evaluate("state.club.source") == "DEMO"
                assert not await evaluate("document.querySelector('#club-view').innerText.includes('LEGENDARY ALLIANCE')")
                empty_club = ClubProfile(tag="#QYQ", name="Empty roster test", members=[], source=DataSource.DEMO)
                empty_payload = {"club":empty_club.model_dump(mode="json"),"analytics":summarize_club_roster(empty_club),"freshness":{"cache_hit":False}}
                await evaluate("renderClub(" + json.dumps(empty_payload) + ")")
                assert await evaluate("document.querySelectorAll('#club-dashboard .ov-card').length") == 13
                assert await evaluate("document.querySelector('#club-members-tbody').innerText.includes('No members returned')")
                assert not await evaluate("/NaN|Infinity/.test(document.querySelector('#club-view').innerText)"), "Invalid empty-roster arithmetic"
                assert await evaluate("document.querySelector('#club-hero-badge-img').classList.contains('hidden')"), "Previous club badge persisted"
                await screenshot("club-empty.png","club-composition")
                await send("Page.navigate", {"url":"http://127.0.0.1:8000/club/%23INVALID"})
                for _ in range(100):
                    if await evaluate("Boolean(document.querySelector('#club-retry'))"):
                        break
                    await asyncio.sleep(.1)
                assert await evaluate("state.club === null && document.querySelector('#club-data-label').innerText === 'UNAVAILABLE'"), "Invalid club replaced by sample data"
                await send("Page.navigate", {"url":"http://127.0.0.1:8000/"})
                await ready()
                print("Club route, charts, planner, member controls, demo and failure recovery checks passed")
                for width in (360, 390, 768):
                    await send("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900,
                                "deviceScaleFactor": 1, "mobile": width == 390})
                    await asyncio.sleep(.3)
                    assert not await evaluate("document.documentElement.scrollWidth > innerWidth"), f"Overflow at {width}"
                    await screenshot(f"{width}-top.png")
                    await screenshot(f"{width}-equipment.png", "ov-equipment")
                    await screenshot(f"{width}-goals.png", "ov-goals")
                await evaluate("loadDemo().then(()=>OverviewDashboard.load())", True)
                await ready()
                assert await evaluate("state.player.source") == "DEMO"
                assert await evaluate("document.querySelector('#overview-view .champ-stat-icon img').src.endsWith('/assets/icon_trophy.png')"), "Previous account's Ranked badge persisted"
                assert await evaluate("document.querySelector('#overview-dashboard').innerText.includes('Ranked information was not returned')")
                assert not await evaluate("document.documentElement.scrollWidth > innerWidth"), "Demo overflow"
                print("Demo states verified")
                # An upstream failure must be retryable without leaving Refresh disabled
                await evaluate("window.originalOverviewFetch=window.fetch;window.fetch=(url,options)=>String(url).includes('/api/overview')?Promise.resolve(new Response(JSON.stringify({error:{message:'Temporary test failure'}}),{status:503,headers:{'Content-Type':'application/json'}})):originalOverviewFetch(url,options);OverviewDashboard.load(true)", True)
                assert await evaluate("document.querySelector('#overview-dashboard').innerText.includes('Temporary test failure')")
                assert not await evaluate("document.querySelector('#overview-refresh').disabled")
                await evaluate("window.fetch=window.originalOverviewFetch;OverviewDashboard.load(true)", True)
                await ready()
                assert not errors, errors
                print("Artwork, sorting, search, refresh, failure recovery, desktop, tablet and mobile checks passed")
                print("Screenshots:", OUTPUT)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    asyncio.run(main())
