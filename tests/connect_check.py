#!/usr/bin/env python3
"""Smoke test: WDA connection and FreeCell foreground launch."""
from __future__ import annotations

import sys

import config
import helpers


def main() -> int:
    errors = config.validate()
    if errors:
        print("CONFIGURATION ERROR:")
        for error in errors:
            print(f"  - {error}")
        return 2
    try:
        print(helpers.wda_status()["value"])
        helpers.connect()
        helpers.launch_app()
        print(f"PASS: launched {config.BUNDLE_ID}")
        print(f"SCREENSHOT: {helpers.screenshot('freecell_smoke')}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
