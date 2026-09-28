#!/usr/bin/env python3
"""About opens from the menu and shows the FreeCell version line."""
from __future__ import annotations

import sys

import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.tap("menu_about", settle=2.0), "About control not found")
    ui.expect(ui.expect_screen("about"), "tapping About did not open About")
    ui.expect(ui.is_on("about_version") or ui.is_on("about_emblem"),
              "About did not show the FreeCell version or emblem")
    shot = ui.shoot("About")
    ui.expect(ui.to_menu(), "could not return to the menu after About")
    print(f"PASS: About opened with the version line and returned — {shot}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
