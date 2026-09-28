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
    "screen_menu": ("qa_menu_enabled", (950, 1270, 1150, 1450)),
    "menu_play": ("subsequent_launch", (900, 1240, 1260, 1420)),
    "menu_daily": ("subsequent_launch", (900, 1420, 1260, 1600)),
    "menu_stats": ("subsequent_launch", (760, 1600, 1260, 1780)),
    "menu_options": ("subsequent_launch", (740, 1780, 1260, 2000)),
    "menu_help": ("subsequent_launch", (900, 2000, 1260, 2200)),
    "menu_about": ("subsequent_launch", (430, 2180, 860, 2360)),
    "more_games": ("subsequent_launch", (0, 1520, 420, 1780)),
    "choose_look": ("subsequent_launch", (0, 1780, 420, 2080)),
    "page_back": ("miss_145_about", (0, 160, 220, 300)),
    "look_close": ("screen_choose_look", (1080, 680, 1260, 860)),
    "stats_solo_tab": ("probe_stats_solo", (40, 340, 520, 500)),
    "stats_daily_tab": ("probe_stats_solo", (620, 340, 1180, 500)),
    "stats_best_zero": ("Stats", (280, 520, 1000, 620)),
    "stats_won_zero": ("Stats", (280, 700, 1000, 780)),
    "stats_easy_none": ("Stats", (280, 920, 1050, 1040)),
    "reset_stats": ("probe_stats_solo_bottom", (200, 2520, 1100, 2740)),
    "reset_solo_stats": ("probe_stats_solo_bottom", (200, 2520, 1100, 2740)),
    "reset_yes": ("miss_113_reset_dialog", (650, 1550, 1100, 1750)),
    "look_surface_tab": ("ChooseLookSurface", (60, 700, 500, 860)),
    "look_cards_tab": ("ChooseLookCards", (500, 700, 980, 860)),
    "daily_back": ("Daily", (0, 170, 300, 340)),
    "screen_daily": ("Daily", (160, 620, 1130, 1000)),
    "difficulty_medium": ("miss_165_picker", (760, 1380, 1260, 1540)),
    "difficulty_hard": ("miss_165_picker", (760, 1540, 1260, 1680)),
    "difficulty_expert": ("miss_165_picker", (760, 1680, 1260, 1860)),
    "difficulty_master": ("miss_165_picker", (760, 1860, 1260, 2000)),
    "screen_stats": ("screen_stats", (400, 100, 950, 350)),
    "screen_options": ("screen_options", (400, 100, 950, 350)),
    "screen_help": ("screen_help", (250, 700, 1000, 1050)),
    "screen_faq": ("screen_faq", (100, 450, 1150, 1500)),
    "screen_about": ("qa_about", (350, 1050, 950, 1450)),
    "screen_more_games": ("screen_more_games", (700, 100, 1250, 500)),
    "screen_choose_look": ("screen_choose_look", (150, 700, 1150, 1050)),
    "screen_choose_look_cards": ("screen_choose_look_cards", (150, 700, 1150, 1900)),
    "screen_options_bottom": ("screen_options_bottom", (0, 650, 1290, 2100)),
    "screen_play": ("qa_picker_clean", (850, 1150, 1250, 1500)),
    "difficulty_easy": ("qa_picker_clean", (850, 1150, 1250, 1450)),
    "screen_table": ("GamePlayTable", (0, 380, 900, 560)),
    "back_game": ("qa_table_started", (0, 290, 260, 410)),
    "table_foundations": ("qa_table_started", (0, 450, 700, 850)),
    "table_cells": ("GamePlayTable", (680, 580, 1280, 760)),
    "tableau": ("GamePlayTable", (0, 2020, 1290, 2180)),
    "about_emblem": ("qa_about_build_info", (500, 450, 800, 800)),
    "about_version": ("qa_about_build_info", (350, 1150, 950, 1400)),
    "qa_watermark": ("qa_menu_enabled", (0, 150, 500, 650)),
    "qa_badge": ("qa_table_started", (1120, 2150, 1290, 2450)),
    "qa_panel": ("qa_panel_table", (400, 850, 1250, 2000)),
    "qa_90_99": ("qa_after_percent", (850, 1600, 1250, 1850)),
    "qa_win": ("qa_after_percent", (550, 1600, 850, 1850)),
    "screen_victory": ("freecell_victory", (100, 1100, 1190, 1260)),
    "victory_title": ("freecell_victory", (380, 930, 910, 1030)),
    "victory_menu": ("screen_victory", (1000, 250, 1270, 500)),
    # First-launch gates, cropped from the 279 walkthrough. WDA cannot see
    # these; they are image-matched only.
    "tc_continue": ("walk_05_after_privacy", (470, 1688, 820, 1788)),
    "tc_terms_link": ("walk_05_after_privacy", (280, 1205, 990, 1320)),
    "tc_privacy_link": ("walk_05_after_privacy", (280, 1345, 990, 1475)),
    "tc_terms_page": ("walk_02_terms_page", (390, 1420, 910, 1500)),
    "tc_privacy_page": ("walk_04_privacy_page", (400, 1230, 890, 1300)),
    "tc_web_close": ("walk_02_terms_page", (20, 140, 160, 280)),
    "att_prompt": ("walk_06_after_continue", (180, 1220, 1110, 1430)),
    "att_allow": ("walk_06_after_continue", (450, 1845, 840, 1915)),
}


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    missing = []
    created = 0
    for name, (source, box) in CROPS.items():
        path = LOG / f"{source}.png"
        if not path.exists():
            missing.append(f"{name} <- {path.name}")
            continue
        Image.open(path).crop(box).save(ASSETS / f"{name}.png")
        created += 1
    if missing:
        print("Missing source captures:")
        print("\n".join(missing))
    print(f"Created {created} FreeCell assets in {ASSETS}")
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
