#!/usr/bin/env python3
"""More Games opens the in-app stage and returns. Does not open the App Store."""
from __future__ import annotations

import sys

from airtest.core.api import swipe

import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.tap("more_games", settle=2.2), "More Games control not found")
    ui.expect(ui.expect_screen("more_games"),
              "tapping More Games did not open the More Games stage")
    shot = ui.shoot("MoreGames")
    swipe((645, 2100), (645, 700), duration=0.6)
    scrolled = ui.shoot("MoreGamesScrolled")
    ui.expect(ui.to_menu(), "could not return to the menu after More Games")
    print(f"PASS: More Games opened, scrolled, and returned — {shot}, {scrolled}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
