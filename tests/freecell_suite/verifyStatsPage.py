#!/usr/bin/env python3
"""verifyStatsPage: Statistics opens, scrolls, returns.

ST-01  Stats opens Statistics and the main menu is gone
ST-03  the page scrolls all the way down to Reset Solo Statistics (not tapped)
ST-04  Back returns to the main menu

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyStatsPage.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402


def _open_stats(c) -> None:
    """Tap Stats; a second tap only when the first left a bare menu (no alert)."""
    ui.expect(ui.tap("menu_stats", settle=2.2), "Stats control not found on the menu")
    if ui.expect_screen("stats", timeout=8.0):
        return
    shot = c.shot(ui.shoot("StatsNotOpened"))
    alert = helpers.alert_text()
    answered = ui.settle_prompts()
    menu = ui.on_menu(1.0)
    print(f"  Statistics did not open (menu up: {menu}, alert: {alert!r}, "
          f"answered: {answered}, see {shot})", flush=True)
    if menu and not alert and ui.tap("menu_stats", settle=2.2) and ui.expect_screen("stats"):
        c.note("the first Stats tap left the menu up with no alert — the second opened it")
        return
    raise AssertionError(f"tapping Stats did not open Statistics (menu up: {menu}, "
                         f"alert: {alert!r}, see {shot})")


def run() -> None:
    fc.menu()
    with caselog.case("ST-01") as c:
        _open_stats(c)
        caselog.step("Check Statistics opened")
        ui.expect(not ui.on_menu(1.0), "the main menu is still showing")
        c.shot(ui.shoot("Stats"))
        c.note("Statistics opened")
    with caselog.case("ST-03") as c:
        ui.open_stats_tab("solo")
        ui.expect(ui.scroll_to_bottom("reset_solo_stats", max_swipes=20),
                  "could not scroll down to Reset Solo Statistics")
        c.shot(ui.shoot("StatsBottom"))
        c.note("Reset Solo Statistics reached at the bottom")
    with caselog.case("ST-04") as c:
        ui.expect(ui.leave_stats(), "Statistics back could not be tapped")
        caselog.step("Check the main menu is showing")
        ui.expect(ui.on_menu(6.0), "Statistics back did not return to the main menu")
        c.note("back on the main menu")
    print("PASS: Statistics opened, scrolled to Reset Solo Statistics, and returned")


if __name__ == "__main__":
    fc.main(run)
