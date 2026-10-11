#!/usr/bin/env python3
"""Kill FreeCell on the table; launch must restore that gameplay screen.

Home backgrounds so the game can save. Then WDA terminate kills the
process. After relaunch the case passes when the gameplay screen is back.
"""
from __future__ import annotations

import sys
import time

import helpers
import freecell_ui as ui

WAIT = 3.5


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.start_game("easy"), "Easy did not reach the table")
    ui.start_deal()
    ui.expect(ui.at_table(), "not on the gameplay screen before the kill")
    before = ui.shoot("RelaunchBeforeKill")

    ui.expect(helpers.home(),
              "Home did not leave the table — the save happens on background")
    print("  backgrounded, now killing the FreeCell process")
    ui.expect(helpers.kill_app(),
              "could not kill the FreeCell process after Home")
    killed_at = time.monotonic()
    time.sleep(WAIT)
    gap = time.monotonic() - killed_at

    ui.expect(ui.relaunch_after_kill(), "could not launch FreeCell again")
    after = ui.shoot("RelaunchAfterKill")
    ui.expect(ui.at_table(timeout=15.0),
              f"the app did not come back on the gameplay screen "
              f"({before} vs {after})")
    print(f"PASS: killed on the table, launched again after {gap:.1f}s, "
          f"and landed on the gameplay screen — {before}, {after}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
