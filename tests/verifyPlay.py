#!/usr/bin/env python3
"""Play opens the picker with FreeCell levels and Easy deals a table."""
from __future__ import annotations

import sys

import helpers
import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.tap("menu_play", settle=2.0), "Play control not found")
    ui.expect(ui.expect_screen("play"), "tapping Play did not open the difficulty picker")
    picker = ui.shoot("PlayPicker")
    missing = [
        level for level in ui.DIFFICULTIES
        if ui.have(f"difficulty_{level}") and not ui.is_on(f"difficulty_{level}")
    ]
    ui.expect(not missing, f"difficulty levels missing from the picker: {missing}")
    ui.expect(ui.is_on("difficulty_easy"), "Easy is missing from the picker")
    ui.expect(ui.tap("difficulty_easy", settle=2.2), "could not tap Easy")
    helpers.accept_alert()
    ui.expect(ui.expect_screen("table", timeout=12.0),
              "choosing Easy did not reach the FreeCell table")
    table = ui.shoot("PlayEasy")
    ui.expect(ui.to_menu(), "could not return to the menu after Play")
    print(f"PASS: Play picker showed levels and Easy dealt a table — {picker}, {table}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
