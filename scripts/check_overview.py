"""Local browser smoke checks and screenshots for the Overview dashboard."""
import asyncio
import base64
import json
import subprocess
import tempfile
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "overview-preview"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


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
