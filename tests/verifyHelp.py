#!/usr/bin/env python3
"""Help opens from the menu, scrolls, and returns."""
from __future__ import annotations

import sys

from airtest.core.api import swipe

import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.tap("menu_help", settle=2.0), "Help control not found")
    ui.expect(ui.expect_screen("help"), "tapping Help did not open Help")
    ui.expect(not ui.on_menu(timeout=1.0), "tapping Help did not leave the menu")
    shot = ui.shoot("Help")
    swipe((645, 2100), (645, 600), duration=0.6)
    swipe((645, 2100), (645, 600), duration=0.6)
    bottom = ui.shoot("HelpBottom")
    ui.expect(ui.to_menu(), "could not return to the menu after Help")
    print(f"PASS: Help opened, scrolled, and returned — {shot}, {bottom}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
