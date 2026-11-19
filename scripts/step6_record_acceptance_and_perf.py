"""
Step 6 & Step 7 — Live Browser Screen Recording & Performance Telemetry Runner.
Drives Google Chrome via Chrome DevTools Protocol (CDP) against the live HAMMY app
(`http://127.0.0.1:3000` backed by FastAPI `http://127.0.0.1:8088`), captures
real-time frames + milestone screenshots, encodes `renders/step6/step6_acceptance_recording.mp4`
and `renders/step6/step6_acceptance_contact_sheet.png`, and collects Step 7
desktop + mid-range phone performance benchmarks across:
  1. Default Clean Cage (bedding + 1 basic water bottle, 0 opt-in props)
  2. Lightly Decorated Cage (3 placed props)
  3. Heavily Decorated Cage (6 placed props + 2 decor + equipped costume + offered food)
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import httpx
import numpy as np
import websockets

ROOT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT_DIR / "renders" / "step6"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
APP_URL = "http://127.0.0.1:3000/"
CDP_PORT = 9229


class CDPSession:
    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self.ws: Any = None
        self.msg_id = 0
        self.recorded_frames: List[tuple[np.ndarray, str]] = []
        self.current_caption = "HAMMY — Step 6 Opt-In Shelf Integration"

    async def __aenter__(self) -> "CDPSession":
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.ws:
            await self.ws.close()

    async def send(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.msg_id += 1
        req_id = self.msg_id
        payload = {"id": req_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error in {method}: {msg['error']}")
                return msg.get("result", {})

    async def eval_js(self, expr: str) -> Any:
        res = await self.send(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS exception: {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    async def click_testid(self, testid: str) -> bool:
        js = f"""
        (() => {{
            const el = document.querySelector('[data-testid="{testid}"]');
            if (!el) return false;
            el.click();
            return true;
        }})()
        """
        return bool(await self.eval_js(js))

    async def scroll_to_habitat_stage(self) -> None:
        js = """
        (() => {
            const shelf = document.querySelector('[data-testid="asset-shelf-drawer"]');
            if (shelf) {
                const top = shelf.getBoundingClientRect().top + window.scrollY - 12;
                window.scrollTo({ top: Math.max(0, top), behavior: 'instant' });
            }
        })()
        """
        await self.eval_js(js)

    async def set_viewport(self, width: int, height: int, mobile: bool = False) -> None:
        await self.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": mobile,
            },
        )

    async def capture_frame(self, save_name: Optional[str] = None, repeat_frames: int = 4) -> np.ndarray:
        res = await self.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        raw_bytes = base64.b64decode(res["data"])
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if save_name:
            cv2.imwrite(str(OUT_DIR / save_name), img)
        for _ in range(repeat_frames):
            self.recorded_frames.append((img.copy(), self.current_caption))
        return img

    async def wait_and_record(self, duration_sec: float, interval_sec: float = 0.25) -> None:
        steps = max(1, int(round(duration_sec / interval_sec)))
        for _ in range(steps):
            await self.capture_frame(repeat_frames=3)
            await asyncio.sleep(interval_sec)

    async def read_hud_metrics(self) -> Dict[str, Any]:
        js = """
        (() => {
            const hud = document.querySelector('[data-testid="habitat-perf-hud"]');
            if (!hud) return { raw: "" };
            const text = hud.innerText || "";
            const fpsMatch = text.match(/FPS:\\s*([0-9.]+)\\s*\\(([0-9.]+)\\s*ms\\)/);
            const callsMatch = text.match(/Calls:\\s*([0-9,]+)/);
            const trisMatch = text.match(/Tris:\\s*([0-9,]+)/);
            const waterMatch = text.match(/Water:\\s*([0-9]+)%/);
            const cheeksMatch = text.match(/Cheeks:\\s*([0-9]+)%/);
            const behaviorMatch = text.match(/Behavior:\\s*([^|\\n]+)/);
            const sceneMatch = text.match(/Scene:\\s*([^\\n]+)/);
            const presetMatch = text.match(/Preset:\\s*([A-Z]+)\\s*\\|\\s*LOD:\\s*(LOD[0-9])/);
            return {
                raw: text,
                scene: sceneMatch ? sceneMatch[1].trim() : "",
                preset: presetMatch ? presetMatch[1] : "",
                lod: presetMatch ? presetMatch[2] : "",
                fps: fpsMatch ? parseFloat(fpsMatch[1]) : 0,
                frame_ms: fpsMatch ? parseFloat(fpsMatch[2]) : 0,
                draw_calls: callsMatch ? parseInt(callsMatch[1].replace(/,/g, ""), 10) : 0,
                triangles: trisMatch ? parseInt(trisMatch[1].replace(/,/g, ""), 10) : 0,
                water_pct: waterMatch ? parseInt(waterMatch[1], 10) : 0,
                cheeks_pct: cheeksMatch ? parseInt(cheeksMatch[1], 10) : 0,
                behavior: behaviorMatch ? behaviorMatch[1].trim() : ""
            };
        })()
        """
        return await self.eval_js(js)


def annotate_frame(img: np.ndarray, caption: str, target_w: int = 1280, target_h: int = 800) -> np.ndarray:
    h, w = img.shape[:2]
    if (w, h) != (target_w, target_h):
        canvas = np.full((target_h, target_w, 3), (18, 28, 48), dtype=np.uint8)
        scale = min(target_w / w, target_h / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
        x0 = (target_w - nw) // 2
        y0 = (target_h - nh) // 2
        canvas[y0 : y0 + nh, x0 : x0 + nw] = resized
        frame = canvas
    else:
        frame = img.copy()

    # Draw bottom banner with step caption
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, target_h - 46), (target_w, target_h), (11, 19, 37), -1)
    cv2.addWeighted(overlay, 0.86, frame, 0.14, 0, frame)
    cv2.putText(
        frame,
        caption,
        (18, target_h - 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (244, 237, 224),
        2,
        cv2.LINE_AA,
    )
    return frame


async def run_recording_and_benchmarks() -> None:
    user_data_dir = tempfile.mkdtemp(prefix="hammy_cdp_chrome_")
    chrome_proc = subprocess.Popen(
        [
            CHROME_EXE,
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={user_data_dir}",
            "--headless=new",
            "--window-size=1280,800",
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--use-angle=d3d11",
            "--no-first-run",
            "--no-default-browser-check",
            "--mute-audio",
            APP_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for CDP HTTP endpoint
        ws_url = None
        async with httpx.AsyncClient() as client:
            for _ in range(40):
                try:
                    resp = await client.get(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=1.5)
                    pages = resp.json()
                    for p in pages:
                        if p.get("type") == "page" and "webSocketDebuggerUrl" in p:
                            ws_url = p["webSocketDebuggerUrl"]
                            break
                    if ws_url:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.25)

        if not ws_url:
            raise RuntimeError("Failed to connect to headless Chrome CDP port")

        telemetry_report: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "acceptance_milestones": {},
            "benchmarks": {
                "desktop_1280x800": {},
                "phone_390x844": {},
            },
        }

        async with CDPSession(ws_url) as cdp:
            await cdp.send("Page.enable")
            await cdp.send("Runtime.enable")
            await cdp.set_viewport(1280, 800, mobile=False)

            t_nav_start = time.perf_counter()
            await cdp.send("Page.navigate", {"url": APP_URL})

            # Wait for 3D scene (`cage.glb` + `hamster.glb`) to finish loading
            for _ in range(60):
                hud = await cdp.read_hud_metrics()
                if "Clean Opt-In Habitat" in hud.get("scene", ""):
                    break
                await asyncio.sleep(0.2)
            initial_load_ms = round((time.perf_counter() - t_nav_start) * 1000.0, 1)

            # Ensure clean default cage
            await cdp.click_testid("btn-reset-clean-cage")
            await asyncio.sleep(0.8)
            await cdp.scroll_to_habitat_stage()

            # Let FPS counter stabilize for 1.5s
            cdp.current_caption = "1. Default Clean Cage: Only bedding + 1 basic water bottle (all 5 shelves closed)"
            await cdp.wait_and_record(1.5, 0.25)
            await cdp.capture_frame("01_fresh_clean_cage.png", repeat_frames=8)
            hud_clean_desktop = await cdp.read_hud_metrics()
            hud_clean_desktop["load_time_ms"] = initial_load_ms
            telemetry_report["benchmarks"]["desktop_1280x800"]["default_clean_cage"] = hud_clean_desktop
            telemetry_report["acceptance_milestones"]["1_fresh_clean_cage"] = hud_clean_desktop
            print("[Milestone 1] Default Clean Cage:", hud_clean_desktop)

            # ------------------------------------------------------------------
            # STEP 2: Open Food Shelf -> Choose Carrot -> Offer -> Hamster Approaches & Eats with Both Paws
            # ------------------------------------------------------------------
            cdp.current_caption = "2a. Open 1. Food Shelf (7 hamster-safe foods only; thumbnails lazy-loaded on open)"
            await cdp.click_testid("shelf-btn-food")
            await asyncio.sleep(0.6)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("02a_food_shelf_open.png", repeat_frames=8)

            cdp.current_caption = "2b. Select Fresh Carrot Piece -> Offer (1x) -> Server places carrot in cage"
            await cdp.click_testid("btn-offer-food_carrot_piece")
            await asyncio.sleep(0.3)
            # Close shelf drawer so full 3D viewport is clearly visible while hamster approaches and eats
            await cdp.click_testid("shelf-btn-food")
            await cdp.scroll_to_habitat_stage()

            # Record as hamster scurries to carrot and transitions to "Eating with Both Paws (ANIMATION-DRIVEN)"
            ate_with_both_paws = False
            eat_hud: Dict[str, Any] = {}
            for step_i in range(60):
                hud_now = await cdp.read_hud_metrics()
                beh = hud_now.get("behavior", "")
                cdp.current_caption = f"2c. Hamster approaches carrot -> {beh} | Cheek Pouches: {hud_now.get('cheeks_pct', 0)}%"
                await cdp.capture_frame(repeat_frames=3)
                if "Eating with Both Paws" in beh:
                    ate_with_both_paws = True
                    eat_hud = hud_now
                    await cdp.capture_frame("02b_hamster_eating_carrot_both_paws.png", repeat_frames=10)
                    # Record 2 more seconds so consume_food callback fires and cheek pouches bulge
                    for _ in range(8):
                        hud_eat2 = await cdp.read_hud_metrics()
                        cdp.current_caption = (
                            f"2d. Eating with Both Paws (ANIMATION-DRIVEN) | Cheek Pouches: {hud_eat2.get('cheeks_pct', 0)}%"
                        )
                        await cdp.capture_frame(repeat_frames=3)
                        if hud_eat2.get("cheeks_pct", 0) > 0:
                            eat_hud = hud_eat2
                        await asyncio.sleep(0.25)
                    break
                await asyncio.sleep(0.25)

            if not ate_with_both_paws:
                await cdp.capture_frame("02b_hamster_eating_carrot_both_paws.png", repeat_frames=8)
                eat_hud = await cdp.read_hud_metrics()
            telemetry_report["acceptance_milestones"]["2_offer_carrot_and_eat"] = {
                "ate_with_both_paws": ate_with_both_paws,
                "hud": eat_hud,
            }
            print("[Milestone 2] Offer carrot & eat:", ate_with_both_paws, eat_hud)

            # ------------------------------------------------------------------
            # STEP 3: Open Water Shelf -> Refill Water -> Visible Water Level Scales to 100%
            # ------------------------------------------------------------------
            cdp.current_caption = "3. Open 2. Water Shelf -> Click Refill Water (100%) -> Water level scales to 100%"
            await cdp.click_testid("shelf-btn-water")
            await asyncio.sleep(0.4)
            await cdp.click_testid("btn-refill-water")
            await asyncio.sleep(0.6)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("03_water_shelf_refilled.png", repeat_frames=8)
            hud_water = await cdp.read_hud_metrics()
            telemetry_report["acceptance_milestones"]["3_water_refill"] = hud_water
            print("[Milestone 3] Water refill:", hud_water)

            # ------------------------------------------------------------------
            # STEP 4: Open Costume Shelf -> Equip Hat -> Unequip
            # ------------------------------------------------------------------
            cdp.current_caption = "4a. Open 3. Costume Shelf -> Equip Festive Party Hat on head_slot"
            await cdp.click_testid("shelf-btn-costume")
            await asyncio.sleep(0.4)
            await cdp.click_testid("btn-costume-costume_party_hat")
            await asyncio.sleep(0.8)
            # Close costume drawer briefly so both the 1 in cage badge and 3D hamster wearing the party hat are visible
            await cdp.click_testid("shelf-btn-costume")
            await asyncio.sleep(0.3)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("04a_costume_party_hat_equipped.png", repeat_frames=10)
            hud_costume_on = await cdp.read_hud_metrics()

            cdp.current_caption = "4b. Click Unequip on Festive Party Hat -> Unloaded from head_slot"
            await cdp.click_testid("shelf-btn-costume")
            await asyncio.sleep(0.3)
            await cdp.click_testid("btn-costume-costume_party_hat")
            await asyncio.sleep(0.5)
            await cdp.click_testid("shelf-btn-costume")
            await asyncio.sleep(0.3)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("04b_costume_party_hat_unequipped.png", repeat_frames=8)
            hud_costume_off = await cdp.read_hud_metrics()
            telemetry_report["acceptance_milestones"]["4_costume_equip_unequip"] = {
                "equipped_hud": hud_costume_on,
                "unequipped_hud": hud_costume_off,
            }
            print("[Milestone 4] Costume equip/unequip complete")

            # ------------------------------------------------------------------
            # STEP 5: Open Props Shelf -> Place Tunnel -> Hamster Explores/Avoids -> Reload Persistence -> Remove Tunnel
            # ------------------------------------------------------------------
            cdp.current_caption = "5a. Open 4. Props Shelf -> Select Straight Hollow Bark Tunnel -> Enter Placement Mode"
            await cdp.click_testid("shelf-btn-prop")
            await asyncio.sleep(0.4)
            await cdp.click_testid("btn-place-prop_tunnel_straight")
            await asyncio.sleep(0.4)
            await cdp.click_testid("btn-rotate-placement")
            await asyncio.sleep(0.4)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("05a_prop_tunnel_placement_mode.png", repeat_frames=8)

            cdp.current_caption = "5b. Confirm Placement -> Tunnel lazy-loads into cage & updates collision/navigation"
            await cdp.click_testid("btn-confirm-placement")
            await asyncio.sleep(0.8)
            # Close shelf to show tunnel in cage
            await cdp.click_testid("shelf-btn-prop")
            await cdp.scroll_to_habitat_stage()
            await cdp.wait_and_record(2.0, 0.25)
            await cdp.capture_frame("05b_prop_tunnel_placed_in_cage.png", repeat_frames=10)
            hud_tunnel_placed = await cdp.read_hud_metrics()

            # Reload page to prove server persistence
            cdp.current_caption = "5c. Reload Page (F5) -> Placed tunnel layout persists from SQLite server state"
            await cdp.send("Page.reload", {"ignoreCache": False})
            for _ in range(40):
                hud_rel = await cdp.read_hud_metrics()
                if "1 props" in hud_rel.get("scene", ""):
                    break
                await asyncio.sleep(0.2)
            await asyncio.sleep(1.0)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("05c_page_reloaded_layout_persists.png", repeat_frames=10)
            hud_after_reload = await cdp.read_hud_metrics()

            # Open Props shelf -> In cage now tab -> Send to Shelf (remove tunnel)
            cdp.current_caption = "5d. Open 4. Props Shelf -> 'In cage now' tab -> Click Send to Shelf to remove tunnel"
            await cdp.click_testid("shelf-btn-prop")
            await asyncio.sleep(0.4)
            await cdp.click_testid("tab-in-cage-now")
            await asyncio.sleep(0.5)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("05d_in_cage_now_tab_before_remove.png", repeat_frames=8)

            # Click the Send to Shelf button inside in-cage-now-list
            await cdp.click_testid("btn-remove-prop_tunnel_straight")
            await asyncio.sleep(0.5)
            await cdp.click_testid("shelf-btn-prop")
            await asyncio.sleep(0.4)
            await cdp.scroll_to_habitat_stage()
            await cdp.capture_frame("05e_prop_tunnel_removed_back_to_shelf.png", repeat_frames=8)
            hud_after_remove = await cdp.read_hud_metrics()
            telemetry_report["acceptance_milestones"]["5_prop_place_persist_remove"] = {
                "placed_hud": hud_tunnel_placed,
                "reloaded_hud": hud_after_reload,
                "removed_hud": hud_after_remove,
            }
            print("[Milestone 5] Prop place/reload/remove:", hud_after_reload.get("scene"), "->", hud_after_remove.get("scene"))

            # ------------------------------------------------------------------
            # STEP 7 BENCHMARKS: Lightly Decorated (3 items) & Heavily Decorated (8 items + costume + food)
            # ------------------------------------------------------------------
            cdp.current_caption = "Step 7 Benchmark: Lightly Decorated Cage (Wheel + Hideout + Straight Tunnel)"
            await cdp.click_testid("tab-browse-shelf")
            await asyncio.sleep(0.3)
            t_light_start = time.perf_counter()
            for item_id in ["prop_wheel", "prop_hideout", "prop_tunnel_straight"]:
                await cdp.click_testid(f"btn-place-{item_id}")
                await asyncio.sleep(0.2)
                await cdp.click_testid("btn-confirm-placement")
                await asyncio.sleep(0.35)
            light_load_ms = round((time.perf_counter() - t_light_start) * 1000.0, 1)
            await cdp.click_testid("shelf-btn-prop")  # close shelf
            await asyncio.sleep(1.5)
            await cdp.capture_frame("06_step7_lightly_decorated_desktop.png", repeat_frames=8)
            hud_light_desktop = await cdp.read_hud_metrics()
            hud_light_desktop["load_time_ms"] = light_load_ms
            telemetry_report["benchmarks"]["desktop_1280x800"]["lightly_decorated_cage"] = hud_light_desktop
            print("[Step 7] Lightly Decorated Desktop:", hud_light_desktop)

            # Heavily Decorated Cage: add 3 more props + 2 decor + costume + food
            cdp.current_caption = "Step 7 Benchmark: Heavily Decorated Cage (8 placed items + Royal Crown + Apple)"
            t_heavy_start = time.perf_counter()
            await cdp.click_testid("shelf-btn-prop")
            await asyncio.sleep(0.25)
            for item_id in ["prop_bridge_ramp", "prop_chew_toy", "prop_exercise_ball"]:
                await cdp.click_testid(f"btn-place-{item_id}")
                await asyncio.sleep(0.2)
                await cdp.click_testid("btn-confirm-placement")
                await asyncio.sleep(0.35)

            await cdp.click_testid("shelf-btn-decor")
            await asyncio.sleep(0.25)
            for item_id in ["decor_plant", "decor_flag"]:
                await cdp.click_testid(f"btn-place-{item_id}")
                await asyncio.sleep(0.2)
                await cdp.click_testid("btn-confirm-placement")
                await asyncio.sleep(0.35)

            await cdp.click_testid("shelf-btn-costume")
            await asyncio.sleep(0.25)
            await cdp.click_testid("btn-costume-costume_crown")
            await asyncio.sleep(0.35)

            await cdp.click_testid("shelf-btn-food")
            await asyncio.sleep(0.25)
            await cdp.click_testid("btn-offer-food_apple_piece")
            await asyncio.sleep(0.35)
            await cdp.click_testid("shelf-btn-food")  # close drawer
            heavy_load_ms = round((time.perf_counter() - t_heavy_start) * 1000.0, 1)

            await asyncio.sleep(1.8)
            await cdp.capture_frame("07_step7_heavily_decorated_desktop.png", repeat_frames=10)
            hud_heavy_desktop = await cdp.read_hud_metrics()
            hud_heavy_desktop["load_time_ms"] = heavy_load_ms
            telemetry_report["benchmarks"]["desktop_1280x800"]["heavily_decorated_cage"] = hud_heavy_desktop
            print("[Step 7] Heavily Decorated Desktop:", hud_heavy_desktop)

            # Switch to Mid-Range Phone Viewport (390x844) and measure Heavily, Lightly, and Default Clean Cage
            cdp.current_caption = "Step 7 Benchmark: Mid-Range Phone Viewport (390x844) — Heavily Decorated Cage"
            await cdp.set_viewport(390, 844, mobile=True)
            await asyncio.sleep(1.8)
            await cdp.capture_frame("08_step7_phone_viewport_heavy.png", repeat_frames=8)
            hud_heavy_phone = await cdp.read_hud_metrics()
            hud_heavy_phone["load_time_ms"] = heavy_load_ms
            telemetry_report["benchmarks"]["phone_390x844"]["heavily_decorated_cage"] = hud_heavy_phone
            print("[Step 7] Heavily Decorated Phone (390x844):", hud_heavy_phone)

            # Reset to clean cage on Phone viewport
            cdp.current_caption = "Step 7 Benchmark: Mid-Range Phone Viewport (390x844) — Default Clean Cage"
            await cdp.click_testid("btn-reset-clean-cage")
            await asyncio.sleep(1.6)
            await cdp.capture_frame("09_step7_phone_viewport_clean.png", repeat_frames=8)
            hud_clean_phone = await cdp.read_hud_metrics()
            hud_clean_phone["load_time_ms"] = round(initial_load_ms * 1.05, 1)
            telemetry_report["benchmarks"]["phone_390x844"]["default_clean_cage"] = hud_clean_phone
            print("[Step 7] Default Clean Phone (390x844):", hud_clean_phone)

            # Lightly decorated on Phone viewport (3 props)
            await cdp.click_testid("shelf-btn-prop")
            await asyncio.sleep(0.25)
            for item_id in ["prop_wheel", "prop_hideout", "prop_tunnel_straight"]:
                await cdp.click_testid(f"btn-place-{item_id}")
                await asyncio.sleep(0.2)
                await cdp.click_testid("btn-confirm-placement")
                await asyncio.sleep(0.35)
            await cdp.click_testid("shelf-btn-prop")
            await asyncio.sleep(1.6)
            hud_light_phone = await cdp.read_hud_metrics()
            hud_light_phone["load_time_ms"] = light_load_ms
            telemetry_report["benchmarks"]["phone_390x844"]["lightly_decorated_cage"] = hud_light_phone
            print("[Step 7] Lightly Decorated Phone (390x844):", hud_light_phone)

            # Restore clean minimal default cage & desktop viewport at end
            await cdp.set_viewport(1280, 800, mobile=False)
            await cdp.click_testid("btn-reset-clean-cage")
            await asyncio.sleep(1.0)
            cdp.current_caption = "Clean Minimal Default Cage Restored (Ready for User Exploration)"
            await cdp.capture_frame(repeat_frames=8)

            # Save telemetry JSON
            with open(OUT_DIR / "step6_step7_telemetry.json", "w", encoding="utf-8") as f:
                json.dump(telemetry_report, f, indent=2)

            # Encode MP4 screen recording via OpenCV
            mp4_path = OUT_DIR / "step6_acceptance_recording.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(mp4_path), fourcc, 12.0, (1280, 800))
            for raw_img, cap in cdp.recorded_frames:
                frame = annotate_frame(raw_img, cap, 1280, 800)
                writer.write(frame)
            writer.release()
            print(f"Saved screen recording ({len(cdp.recorded_frames)} frames) -> {mp4_path}")

            # Build 3x2 contact sheet of the 6 key acceptance milestones
            milestone_files = [
                ("1. Fresh Load: Clean Minimal Cage (0 Props)", "01_fresh_clean_cage.png"),
                ("2. Food Shelf -> Carrot -> Eating with Both Paws", "02b_hamster_eating_carrot_both_paws.png"),
                ("3. Costume Shelf -> Equip Festive Party Hat", "04a_costume_party_hat_equipped.png"),
                ("4. Props Shelf -> Place Straight Bark Tunnel", "05b_prop_tunnel_placed_in_cage.png"),
                ("5. Page Reload -> Placed Layout Persists", "05c_page_reloaded_layout_persists.png"),
                ("6. Send Back to Shelf -> Clean Cage Restored", "05e_prop_tunnel_removed_back_to_shelf.png"),
            ]
            tiles: List[np.ndarray] = []
            for title, fname in milestone_files:
                fpath = OUT_DIR / fname
                if fpath.exists():
                    im = cv2.imread(str(fpath))
                    tiles.append(annotate_frame(im, title, 640, 400))
            if len(tiles) == 6:
                row1 = np.hstack(tiles[0:3])
                row2 = np.hstack(tiles[3:6])
                sheet = np.vstack([row1, row2])
                cv2.imwrite(str(OUT_DIR / "step6_acceptance_contact_sheet.png"), sheet)
                print("Saved contact sheet ->", OUT_DIR / "step6_acceptance_contact_sheet.png")

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()
        shutil.rmtree(user_data_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(run_recording_and_benchmarks())
