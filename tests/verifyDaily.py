#!/usr/bin/env python3
"""Daily opens the calendar and can return to the menu.

Does not deal a date — picking a day starts a table and can fire an
interstitial, which the offline suite must not depend on.
"""
from __future__ import annotations

import sys

import helpers
import freecell_ui as ui


def _open_calendar() -> None:
    ui.expect(ui.tap("menu_daily", settle=2.2), "Daily control not found")
    if ui.seen("screen_daily", timeout=2.5):
        return
    # First visit draws two tip cards over the calendar.
    helpers.wda_tap((645, 900), settle=1.0)
    helpers.wda_tap((645, 900), settle=1.0)
    ui.expect(ui.seen("screen_daily", timeout=6.0),
              "tapping Daily did not open the calendar")


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    _open_calendar()
    ui.expect(not ui.on_menu(timeout=1.0), "tapping Daily did not leave the menu")
    ui.expect(ui.is_on("daily_back") or ui.is_on("page_back"),
              "Daily calendar is missing its back control")
    shot = ui.shoot("Daily")
    ui.expect(ui.leave_daily() or ui.tap("daily_back", settle=1.6),
              "could not tap Daily back")
    ui.expect(ui.on_menu(timeout=6.0) or ui.to_menu(),
              "could not return to the menu after Daily")
    print(f"PASS: Daily calendar opened and returned to the menu — {shot}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
