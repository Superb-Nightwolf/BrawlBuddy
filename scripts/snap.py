import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import httpx
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

async def take_screenshot(url: str, output_path: str, width: int = 1280, height: int = 900, wait_time: float = 2.0):
    user_data_dir = tempfile.mkdtemp(prefix="chrome_snap_")
    port = 9222
    proc = subprocess.Popen([
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        f"--window-size={width},{height}",
        "--disable-gpu",
        "--hide-scrollbars",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        # Wait for CDP to be ready
        async with httpx.AsyncClient() as client:
            ws_url = None
            for _ in range(30):
                await asyncio.sleep(0.2)
                try:
                    res = await client.get(f"http://127.0.0.1:{port}/json/list")
                    pages = res.json()
                    if pages:
                        ws_url = pages[0].get("webSocketDebuggerUrl")
                        if ws_url:
                            break
                except Exception:
                    pass

        if not ws_url:
            raise RuntimeError("Failed to connect to Chrome CDP")

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            msg_id = 1

            async def send(method, params=None):
                nonlocal msg_id
                mid = msg_id
                msg_id += 1
                await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                while True:
                    resp = json.loads(await ws.recv())
                    if resp.get("id") == mid:
                        return resp.get("result", {})

            await send("Page.enable")
            await send("Emulation.setDeviceMetricsOverride", {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": width <= 680,
            })
            await send("Page.navigate", {"url": url})
            await asyncio.sleep(wait_time)

            result = await send("Page.captureScreenshot", {"format": "png"})
            data = base64.b64decode(result["data"])
            with open(output_path, "wb") as f:
                f.write(data)
            print(f"Captured {output_path} ({len(data)} bytes)")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        shutil.rmtree(user_data_dir, ignore_errors=True)

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/#/brawlers/16000040"
    out = sys.argv[2] if len(sys.argv) > 2 else "temp_snap.png"
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
    h = int(sys.argv[4]) if len(sys.argv) > 4 else 900
    asyncio.run(take_screenshot(url, out, width=w, height=h))
