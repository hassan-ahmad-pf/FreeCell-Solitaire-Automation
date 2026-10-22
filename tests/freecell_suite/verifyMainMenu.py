#!/usr/bin/env python3
"""verifyMainMenu: every main-menu control is on screen.

MM-01  Play, Daily, Stats, Options, Help, About, More Games, Choose Look and
       the crown logo are all visible once the menu has finished animating

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyMainMenu.py
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

CONTROLS = ui.MENU_ITEMS + ("menu_logo",)


def run() -> None:
    fc.menu()
    with caselog.case("MM-01") as c:
        caselog.step(f"Check the {len(ui.MENU_ITEMS)} main-menu buttons and the FreeCell logo show")
        deadline = time.time() + 20.0
        missing = list(CONTROLS)
        while missing and time.time() < deadline:
            missing = [name for name in CONTROLS if not ui.is_on(name)]
            if missing:
                time.sleep(0.5)
        c.shot(ui.shoot("MainMenu"))
        ui.expect(not missing, f"main-menu controls never all appeared: {missing}")
        c.note(f"all {len(CONTROLS)} controls visible")
    print(f"PASS: the main menu shows all {len(CONTROLS)} controls")


if __name__ == "__main__":
    fc.main(run)
