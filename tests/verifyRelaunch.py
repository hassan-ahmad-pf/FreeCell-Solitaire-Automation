#!/usr/bin/env python3
"""Kill the FreeCell process on the table; launch must restore that table.

Home is only the save (background). Then WDA terminate kills the process.
A Home-only background is not this case. A kill without Home comes back
on the menu and does not measure the product.
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

    # Home only backgrounds so the game can save. The case is a full kill.
    ui.expect(helpers.home(),
              "Home did not leave the table — the save happens on background")
    print("  backgrounded, now killing the FreeCell process")
    ui.expect(helpers.kill_app(),
              f"FreeCell was still running after terminate "
              f"(state {helpers.app_state()}) — that is a background, not a kill")
    print(f"  process is dead (state {helpers.app_state()})")
    killed_at = time.monotonic()
    time.sleep(WAIT)
    gap = time.monotonic() - killed_at

    ui.expect(ui.relaunch_after_kill(), "could not launch FreeCell again")
    after = ui.shoot("RelaunchAfterKill")
    ui.expect(helpers.in_app(),
              f"FreeCell is not in front after relaunch "
              f"({helpers.active_app() or 'unknown'} is) — {after}")
    ui.expect(not ui.on_menu(1.5),
              f"the app came back on the main menu, not the table "
              f"({before} vs {after})")
    ui.expect(ui.at_table(timeout=15.0),
              f"the app did not come back on the gameplay screen that "
              f"was killed ({before} vs {after})")
    print(f"PASS: killed on the table, launched again after {gap:.1f}s, "
          f"and landed on the same gameplay screen — {before}, {after}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
