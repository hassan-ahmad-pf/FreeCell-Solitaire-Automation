"""Small WDA/Airtest helpers shared by the FreeCell tests."""
from __future__ import annotations

import time
from pathlib import Path

import requests
from airtest.core.api import connect_device, snapshot, touch

import config


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
        f"{config.WDA_URL}/wda/apps/launch",
        json={"bundleId": config.BUNDLE_ID, "shouldLaunch": True, "forceAppLaunch": force},
        timeout=15,
    )
    response.raise_for_status()
    time.sleep(2.5)


def tap(point: tuple[int, int], settle: float = 1.0) -> None:
    touch(point)
    if settle:
        time.sleep(settle)


def screenshot(name: str) -> Path:
    """Capture the current device frame into the ignored log directory."""
    config.LOG.mkdir(parents=True, exist_ok=True)
    path = config.LOG / f"{name}.png"
    snapshot(filename=str(path))
    return path
