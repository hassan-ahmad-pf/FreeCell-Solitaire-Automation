#!/usr/bin/env python3
"""The main menu shows Play, Daily, Stats, Options, Help, About, More Games, Choose Look."""
from __future__ import annotations

import sys
import time

import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "did not reach the main menu after launch")
    deadline = time.time() + 20.0
    missing = list(ui.MENU_ITEMS)
    while time.time() < deadline:
        missing = [name for name in ui.MENU_ITEMS if not ui.is_on(name)]
        if not missing:
            break
        time.sleep(0.4)
    ui.expect(not missing, f"main-menu controls never all appeared: {missing}")
    shot = ui.shoot("MainMenu")
    print(f"PASS: main menu shows all {len(ui.MENU_ITEMS)} controls — {shot}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
