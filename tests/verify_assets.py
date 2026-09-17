#!/usr/bin/env python3
"""Offline gate for the first FreeCell anchor set."""
from __future__ import annotations

import sys

from PIL import Image

import config


REQUIRED = (
    "screen_menu",
    "menu_play",
    "screen_stats",
    "screen_options",
    "screen_help",
    "screen_about",
    "screen_more_games",
    "screen_choose_look",
    "screen_play",
    "difficulty_easy",
    "screen_table",
    "table_foundations",
    "table_cells",
    "tableau",
    "back_game",
    "qa_watermark",
    "qa_badge",
    "qa_panel",
    "qa_90_99",
    "qa_win",
    "screen_victory",
    "victory_title",
    "victory_menu",
)


def main() -> int:
    missing = []
    invalid = []
    for name in REQUIRED:
        path = config.ASSETS / f"{name}.png"
        if not path.exists():
            missing.append(name)
            continue
        try:
            width, height = Image.open(path).size
            if width < 5 or height < 5:
                invalid.append(f"{name} ({width}x{height})")
        except Exception as exc:  # noqa: BLE001
            invalid.append(f"{name} ({exc})")
    if missing or invalid:
        if missing:
            print("Missing:", ", ".join(missing))
        if invalid:
            print("Invalid:", ", ".join(invalid))
        return 1
    print(f"PASS: {len(REQUIRED)} FreeCell anchors are readable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
