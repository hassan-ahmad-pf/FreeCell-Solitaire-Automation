#!/usr/bin/env python3
"""Keep iproxy up while xcodebuild is alive. Never relaunches XCTest."""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PIDFILE = Path(os.environ.get("WDA_PIDFILE", ROOT / "log" / "wda.pids"))
PORT = os.environ.get("WDA_PORT", "8100")
STATUS = f"http://127.0.0.1:{PORT}/status"


def _xcode_alive() -> bool:
    if not PIDFILE.exists():
        return False
    text = PIDFILE.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("WDA_PID="):
            pid = line.split("=", 1)[1].strip()
            try:
                os.kill(int(pid), 0)
                return True
            except Exception:  # noqa: BLE001
                return False
    return False


def _up() -> bool:
    try:
        requests.get(STATUS, timeout=2).raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        return False


def _restart_iproxy() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    import helpers  # noqa: WPS433

    helpers.restart_iproxy()


def main() -> int:
    while True:
        time.sleep(6)
        if _up():
            continue
        if not _xcode_alive():
            continue
        _restart_iproxy()


if __name__ == "__main__":
    raise SystemExit(main())
