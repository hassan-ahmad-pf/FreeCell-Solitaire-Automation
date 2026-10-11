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
