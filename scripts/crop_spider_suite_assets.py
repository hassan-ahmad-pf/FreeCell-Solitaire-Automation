#!/usr/bin/env python3
"""Cut the templates the Spider-suite ports need from log/spider_src/ captures.

The captures come from scripts/spider_explore.py on the 1290x2796 iPhone.
Only names listed here are written; existing assets are never touched.

    ./.venv/bin/python scripts/crop_spider_suite_assets.py            # write
    ./.venv/bin/python scripts/crop_spider_suite_assets.py --preview  # sheet only
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "log" / "spider_src"
ASSETS = ROOT / "assets"

CROPS = {
    "menu_logo": ("menu", (460, 420, 800, 700)),
    "about_help": ("about", (540, 1700, 750, 1785)),
    "about_adfree": ("about", (400, 1815, 885, 1895)),
    "about_faq": ("about", (225, 1928, 1065, 2008)),
    "about_more_games": ("about", (450, 2042, 835, 2122)),
    "about_feedback": ("about", (385, 2150, 900, 2232)),
    "faq_feedback": ("faq_end", (355, 2378, 930, 2452)),
    "help_faq_link": ("help_end", (178, 2378, 1110, 2454)),
    "contact_us": ("options_top", (975, 205, 1260, 285)),
    "mg_cardgames": ("more_games_swiped", (465, 1490, 765, 1777)),
    "mg_spiderette": ("more_games_swiped", (492, 2132, 711, 2405)),
    "drawer_replay": ("table_drawer", (300, 1950, 590, 2030)),
    "drawer_abandon": ("table_drawer", (760, 1950, 1100, 2030)),
    "drawer_new": ("table_drawer", (790, 2095, 1060, 2175)),
    "drawer_help": ("table_drawer", (330, 2235, 560, 2315)),
    "drawer_faq": ("table_drawer", (800, 2235, 1060, 2315)),
    "hint_more": ("play_hint_1", (905, 2040, 1225, 2100)),
    "resume": ("picker_paused", (860, 2075, 1135, 2180)),
    "ad_close": ("ad_tree", (62, 223, 114, 275)),
    "hint_lower": ("table_fresh", (525, 2084, 764, 2128)),
    "faq_header": ("faq_bottom", (540, 190, 750, 290)),
    "mg_header": ("more_games_scrolled", (860, 200, 1260, 320)),
    "promo_close": ("house_promo", (1110, 570, 1182, 644)),
    "hint_deck": ("table_hint", (935, 2340, 1205, 2450)),
    "victory_ranking": ("dev_victory_3", (540, 895, 750, 945)),
    "victory_leaderboards": ("dev_victory_3", (225, 1752, 575, 1812)),
    "victory_achieve": ("dev_victory_3", (725, 1752, 1090, 1812)),
    "victory_help": ("dev_victory_3", (113, 2212, 441, 2342)),
    "victory_new": ("dev_victory_3", (481, 2212, 809, 2342)),
    "victory_stats": ("dev_victory_3", (850, 2212, 1178, 2342)),
    "victory_level_easy": ("dev_victory_3", (335, 2065, 585, 2125)),
    "qa_badge_a": ("dev_table_qa", (1220, 2250, 1270, 2300)),
    "screen_last_score": ("dev_last_score", (330, 210, 960, 285)),
    "last_score_next": ("dev_last_score", (1020, 1036, 1074, 1084)),
    "gc_back": ("dev_gc_leaderboards", (55, 190, 175, 310)),
    "gc_leaderboards": ("dev_gc_leaderboards", (55, 500, 725, 585)),
    "gc_achievements": ("dev_gc_achievements", (55, 500, 745, 585)),
    "qa_watermark": ("dev_menu_qa", (40, 255, 410, 320)),
    "qa_page_adapters": ("dev_qa_page", (150, 1400, 520, 1462)),
    "qa_page_back": ("dev_qa_page", (18, 200, 215, 268)),
    "about_reset_alerts": ("dev_about_qa", (1100, 2515, 1232, 2615)),
    "ad_open_store": ("dev_ad_open_store", (60, 222, 315, 276)),
    # Daily (FreeCell's own DY cases)
    "daily_tip1": ("daily_tip1", (232, 683, 1066, 833)),
    "daily_tip2": ("daily_tip2", (205, 465, 1080, 607)),
    "daily_weekdays": ("daily_won", (82, 1180, 1203, 1245)),
    "daily_faq_link": ("daily_won", (585, 2148, 705, 2207)),
    "daily_gold_star": ("daily_won", (755, 1548, 843, 1631)),
    "daily_levels": ("daily_levels", (645, 402, 1252, 1867)),
    "daily_relaxed_note": ("daily_levels", (50, 1745, 550, 2080)),
    "daily_level_easy": ("daily_level_easy", (960, 280, 1150, 352)),
    "daily_level_medium": ("daily_level_medium", (864, 267, 1149, 330)),
    "daily_level_hard": ("daily_level_hard", (971, 280, 1150, 340)),
    "daily_level_easy_r": ("daily_level_easy_r", (899, 270, 1148, 352)),
    "daily_table_star": ("daily_table_past", (605, 306, 686, 383)),
    "daily_table_medium": ("daily_table_today", (315, 1781, 975, 1828)),
    "daily_popup_days": ("daily_score_popup", (375, 590, 460, 760)),
    "faq_daily_heading": ("daily_faq", (265, 636, 1025, 722)),
}


def preview() -> Path:
    tiles = []
    for name, (source, box) in CROPS.items():
        tile = Image.open(SRC / f"{source}.png").convert("RGB").crop(box)
        tiles.append((name, tile))
    width = max(t.width for _, t in tiles) + 20
    height = sum(t.height + 40 for _, t in tiles)
    sheet = Image.new("RGB", (width, height), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    y = 0
    for name, tile in tiles:
        draw.text((10, y + 8), name, fill=(255, 255, 0))
        sheet.paste(tile, (10, y + 30))
        y += tile.height + 40
    out = SRC / "crops_preview.png"
    sheet.save(out)
    return out


def main() -> int:
    if "--preview" in sys.argv[1:]:
        print(f"wrote {preview()}")
        return 0
    for name, (source, box) in CROPS.items():
        out = ASSETS / f"{name}.png"
        if out.exists():
            print(f"  keep  {out.name} (already exists)")
            continue
        Image.open(SRC / f"{source}.png").convert("RGB").crop(box).save(out)
        print(f"  wrote {out.name}  {box} from {source}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
