#!/usr/bin/env python3
"""Options opens from the menu, scrolls, and returns."""
from __future__ import annotations

import sys

import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.tap("menu_options", settle=2.0), "Options control not found")
    ui.expect(ui.expect_screen("options"), "tapping Options did not open Options")
    shot = ui.shoot("Options")
    ui.scroll()
    ui.scroll()
    bottom = ui.shoot("OptionsBottom")
    ui.expect(ui.to_menu(), "could not return to the menu after Options")
    print(f"PASS: Options opened, scrolled, and returned — {shot}, {bottom}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
