#!/usr/bin/env python3
"""Create the first FreeCell anchor set from the live walkthrough captures."""
from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "log"
ASSETS = ROOT / "assets"

# Coordinates are capture pixels for the connected 1290x2796 iPhone. Crops are
# deliberately small semantic anchors, not whole-screen baselines.
CROPS = {
    "screen_menu": ("qa_about_recovered", (850, 1150, 1250, 1500)),
    "menu_play": ("qa_about_recovered", (850, 1150, 1250, 1500)),
    "menu_stats": ("qa_about_recovered", (800, 1550, 1250, 1850)),
    "menu_options": ("qa_about_recovered", (800, 1800, 1250, 2100)),
    "menu_help": ("qa_about_recovered", (800, 2050, 1250, 2300)),
    "menu_about": ("qa_about_recovered", (400, 2200, 900, 2450)),
    "more_games": ("qa_about_recovered", (0, 1550, 500, 2100)),
    "choose_look": ("qa_about_recovered", (0, 1850, 500, 2200)),
    "screen_stats": ("screen_stats", (400, 100, 950, 350)),
    "screen_options": ("screen_options", (400, 100, 950, 350)),
    "screen_help": ("screen_help", (250, 700, 1000, 1050)),
    "screen_about": ("qa_about", (350, 1050, 950, 1450)),
    "screen_more_games": ("screen_more_games", (700, 100, 1250, 500)),
    "screen_choose_look": ("screen_choose_look", (150, 700, 1150, 1050)),
    "screen_play": ("qa_picker_clean", (850, 1150, 1250, 1500)),
    "difficulty_easy": ("qa_picker_clean", (850, 1150, 1250, 1450)),
    "screen_table": ("qa_table_started", (0, 250, 1290, 900)),
    "table_foundations": ("qa_table_started", (0, 450, 700, 850)),
    "table_cells": ("qa_table_started", (650, 450, 1290, 850)),
    "tableau": ("qa_table_started", (0, 850, 1290, 1550)),
    "about_emblem": ("qa_about_build_info", (500, 450, 800, 800)),
    "about_version": ("qa_about_build_info", (350, 1150, 950, 1400)),
    "qa_watermark": ("qa_menu_enabled", (0, 150, 500, 650)),
    "qa_badge": ("qa_table_started", (1120, 2150, 1290, 2450)),
    "qa_panel": ("qa_panel_table", (400, 850, 1250, 2000)),
    "qa_90_99": ("qa_after_percent", (850, 1600, 1250, 1850)),
    "qa_win": ("qa_after_percent", (550, 1600, 850, 1850)),
    "victory_title": ("screen_victory", (400, 850, 950, 1800)),
    "victory_menu": ("screen_victory", (1000, 250, 1270, 500)),
}


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    missing = []
    for name, (source, box) in CROPS.items():
        path = LOG / f"{source}.png"
        if not path.exists():
            missing.append(str(path))
            continue
        Image.open(path).crop(box).save(ASSETS / f"{name}.png")
    if missing:
        print("Missing source captures:")
        print("\n".join(missing))
        return 2
    print(f"Created {len(CROPS)} FreeCell assets in {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
