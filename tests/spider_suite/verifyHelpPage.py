#!/usr/bin/env python3
"""Spider's verifyHelpPage on FreeCell: Help opens, its rules scroll, Back returns.

HP-01  Help opens and the main menu is gone
HP-02  the rules scroll down to the frequently asked questions link
HP-03  Back returns to the main menu

Run:  ./.venv/bin/python -u tests/spider_suite/verifyHelpPage.py
"""
from __future__ import annotations

import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

MAX_SWIPES = 25


def scroll_until(name: str, max_swipes: int = MAX_SWIPES) -> bool:
    for _ in range(max_swipes):
        if ui.is_on(name):
            return True
        try:
            ui.scroll(True)
        except requests.RequestException:
            # WDA answers a swipe only once the app idles; a busy page can
            # outlast the request timeout while the swipe itself still lands.
            time.sleep(3.0)
        ui.settle(3.0)
    return ui.is_on(name)


def run() -> None:
    fc.menu()
    with caselog.case("HP-01") as c:
        ui.expect(ui.tap("menu_help", settle=2.2), "Help control not found on the menu")
        ui.expect(ui.expect_screen("help"), "tapping Help did not open Help")
        ui.expect(not ui.on_menu(1.0), "the main menu is still showing")
        c.shot(ui.shoot("Help"))
        c.note("Help opened")
    with caselog.case("HP-02") as c:
        ui.expect(scroll_until("help_faq_link"),
                  "the frequently asked questions link never came into view")
        c.shot(ui.shoot("HelpBottom"))
        c.note("scrolled down to the FAQ link")
    with caselog.case("HP-03") as c:
        ui.back()
        ui.expect(ui.on_menu(6.0), "Help back did not return to the main menu")
        c.note("back on the main menu")
    print("PASS: Help opened, scrolled to its FAQ link, and returned")


if __name__ == "__main__":
    fc.main(run)
