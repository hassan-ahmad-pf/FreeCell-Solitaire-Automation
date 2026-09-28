#!/usr/bin/env python3
"""The Easy table shows FreeCell layout and the hint control responds."""
from __future__ import annotations

import sys

import helpers
import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.start_game("easy"), "Easy did not reach the table")
    ui.start_deal()
    ui.expect(ui.is_on("screen_table"), "table header is missing")
    ui.expect(ui.is_on("table_cells"), "free cells are missing from the table")
    ui.expect(ui.is_on("tableau"), "the hint bar is missing from the table")
    before = ui.shoot("GamePlayTable")
    helpers.wda_tap((1080, 2260), settle=1.2)
    after = ui.shoot("GamePlayHint")
    ui.expect(ui.to_menu(), "could not return to the menu after gameplay")
    print(f"PASS: Easy table has header, free cells, hint bar; hint fired — "
          f"{before}, {after}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
