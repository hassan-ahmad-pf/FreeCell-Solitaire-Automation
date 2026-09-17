"""Small WDA/Airtest helpers shared by the FreeCell tests."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from airtest.core.api import connect_device, snapshot, touch

import config


_SESSION_ID: str | None = None


def wda_status() -> dict:
    """Return WDA status or raise a useful connection error."""
    response = requests.get(f"{config.WDA_URL}/status", timeout=5)
    response.raise_for_status()
    return response.json()


def connect() -> None:
    """Attach Airtest to the already-running WDA session."""
    connect_device(config.DEVICE_URI)


def launch_app(force: bool = False) -> None:
    """Launch FreeCell through WDA, never Airtest's iOS start_app."""
    response = requests.post(
        f"{config.WDA_URL}/session",
        json={
            "capabilities": {
                "alwaysMatch": {
                    "bundleId": config.BUNDLE_ID,
                    "forceAppLaunch": force,
                    "shouldTerminateApp": False,
                }
            }
        },
        timeout=15,
    )
    response.raise_for_status()
    global _SESSION_ID
    _SESSION_ID = response.json()["value"]["sessionId"]
    time.sleep(2.5)


def tap(point: tuple[int, int], settle: float = 1.0) -> None:
    touch(point)
    if settle:
        time.sleep(settle)


def current_session() -> str:
    if not _SESSION_ID:
        raise RuntimeError("launch_app() must run before WDA actions")
    return _SESSION_ID


def accept_alert() -> bool:
    """Accept a native confirmation if WDA currently exposes one."""
    response = requests.get(
        f"{config.WDA_URL}/session/{current_session()}/alert/text",
        timeout=8,
    )
    if response.status_code != 200 or not response.json().get("value"):
        return False
    accepted = requests.post(
        f"{config.WDA_URL}/session/{current_session()}/alert/accept",
        timeout=8,
    )
    accepted.raise_for_status()
    time.sleep(1.5)
    return True


def rapid_tap(point: tuple[int, int], times: int = 10, gap_ms: int = 45) -> bool:
    """Send a hidden-gesture tap burst as one on-device W3C action."""
    from PIL import Image

    pixel_width = Image.open(screenshot("_qa_scale_probe")).width
    point_width = requests.get(
        f"{config.WDA_URL}/session/{current_session()}/window/size",
        timeout=15,
    ).json()["value"]["width"]
    scale = max(pixel_width / float(point_width), 1.0)
    x, y = int(point[0] / scale), int(point[1] / scale)
    actions = [{"type": "pointerMove", "duration": 0, "x": x, "y": y}]
    for _ in range(times):
        actions.extend((
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 25},
            {"type": "pointerUp", "button": 0},
            {"type": "pause", "duration": gap_ms},
        ))
    response = requests.post(
        f"{config.WDA_URL}/session/{current_session()}/actions",
        data=json.dumps({"actions": [{
            "type": "pointer",
            "id": "freecell-qa",
            "parameters": {"pointerType": "touch"},
            "actions": actions,
        }]}),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    time.sleep(1.5)
    return True


def screenshot(name: str) -> Path:
    """Capture the current device frame into the ignored log directory."""
    config.LOG.mkdir(parents=True, exist_ok=True)
    path = config.LOG / f"{name}.png"
    snapshot(filename=str(path))
    return path
