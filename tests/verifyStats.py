#!/usr/bin/env python3
"""Statistics opens from the menu and returns."""
from __future__ import annotations

import sys

from airtest.core.api import swipe

import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.tap("menu_stats", settle=2.0), "Stats control not found")
    ui.expect(ui.expect_screen("stats"), "tapping Stats did not open Statistics")
    shot = ui.shoot("Stats")
    swipe((645, 2100), (645, 700), duration=0.6)
    bottom = ui.shoot("StatsBottom")
    ui.expect(ui.to_menu(), "could not return to the menu after Stats")
    print(f"PASS: Statistics opened, scrolled, and returned — {shot}, {bottom}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
