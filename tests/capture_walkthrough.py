#!/usr/bin/env python3
"""Capture the fresh FreeCell walkthrough for asset authoring.

This is intentionally a guided capture: navigation coordinates and semantic
assets are not guessed from Spider. Run it with the device visible and record
the screen names printed by the script before cropping assets.
"""
from __future__ import annotations

import sys
import time

import config
import helpers


CAPTURES = (
    "01_launch_terms",
    "02_main_menu",
    "03_play_entry",
    "04_stats",
    "05_options",
    "06_help",
    "07_about",
    "08_more_games",
    "09_choose_look",
    "10_table",
)


def main() -> int:
    if config.validate():
        print("Set DEVICE_UDID and create the FreeCell assets directory first.")
        return 2
    try:
        helpers.connect()
        helpers.launch_app(force=False)
        for name in CAPTURES:
            path = helpers.screenshot(name)
            print(f"{name}: {path}")
            print("  Navigate to the next named screen, then press Enter.")
            input()
        print("Capture walkthrough complete. Crop only FreeCell screenshots into assets/.")
        return 0
    except KeyboardInterrupt:
        print("\nCapture stopped.")
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
