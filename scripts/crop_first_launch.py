#!/usr/bin/env python3
"""Crop first-launch FreeCell gates from the 279 walkthrough captures."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "log"
ASSETS = ROOT / "assets"

CROPS = {
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
    for name, (source, box) in CROPS.items():
        path = LOG / f"{source}.png"
        if not path.exists():
            missing.append(f"{name} <- {path}")
            continue
        out = ASSETS / f"{name}.png"
        Image.open(path).crop(box).save(out)
        print(f"{name}: {out} {Image.open(out).size}")
    if missing:
        print("Missing:")
        print("\n".join(missing))
        return 2
    print(f"Created {len(CROPS)} first-launch assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
