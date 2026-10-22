#!/usr/bin/env python3
"""verifyFreeCellLogo: About by menu item and by the crown logo.

AB-01  About opens from the About menu item
AB-03  the version line and the help / ad free / FAQ / more games / feedback
       links are on the page (the links that leave the app are not tapped)
AB-04  frequently asked questions opens FAQ inside FreeCell
AB-05  FAQ scrolls down to submit feedback and stays on FAQ
AB-06  the crown logo also opens About

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyFreeCellLogo.py
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
from verifyHelpPage import scroll_until  # noqa: E402

LINKS = ("about_version", "about_help", "about_adfree", "about_faq",
         "about_more_games", "about_feedback")
# The FAQ text below its pinned header, in px.
FAQ_BAND = (0, 391, 1290, 2628)
# A swipe changes over a quarter of the text; a page that did not move, ~0.
MOVED = 0.05


def run() -> None:
    fc.menu()
    with caselog.case("AB-01") as c:
        ui.expect(ui.tap("menu_about", settle=2.5), "About control not found on the menu")
        caselog.step("Check the About page opened")
        ui.expect(ui.expect_screen("about"), "tapping About did not open About")
        c.shot(ui.shoot("About"))
        c.note("About opened from the menu item")
    with caselog.case("AB-03") as c:
        caselog.step("Check About shows the version line and its five links (Help, Ad-Free, "
                     "FAQ, More Games, Feedback)")
        missing = [name for name in LINKS if not ui.is_on(name)]
        ui.expect(not missing, f"About is missing {missing}")
        c.note("version line and all five links present")
    with caselog.case("AB-04") as c:
        ui.expect(ui.tap("about_faq", settle=2.5), "frequently asked questions could not be tapped")
        caselog.step("Check the FAQ opened inside FreeCell")
        ui.expect(helpers.in_app(), f"FAQ left FreeCell for {helpers.active_app()}")
        ui.expect(ui.seen("screen_faq", timeout=8.0), "FAQ did not open")
        c.shot(ui.shoot("AboutFaq"))
        c.note("FAQ opened inside FreeCell")
    with caselog.case("AB-05") as c:
        top = ui.shoot("_faq_top")
        ui.expect(scroll_until("faq_feedback"), "submit feedback never came into view on FAQ")
        end = c.shot(ui.shoot("AboutFaqBottom"))
        caselog.step("Check the FAQ text moved and the page is still the FAQ")
        moved = fc.diff_frac(top, end, FAQ_BAND)
        ui.expect(moved >= MOVED, f"the FAQ did not scroll — only {moved:.1%} of its text "
                                  "changed")
        ui.expect(ui.is_on("faq_header"), "scrolling the FAQ navigated away from it")
        c.note(f"scrolled to submit feedback ({moved:.0%} of the text changed), still on FAQ")
    ui.back()
    ui.expect(ui.expect_screen("about", timeout=6.0), "FAQ back did not return to About")
    ui.back()
    ui.expect(ui.on_menu(6.0), "About back did not return to the main menu")
    with caselog.case("AB-06") as c:
        ui.expect(ui.tap("menu_logo", settle=2.5), "the crown logo could not be tapped")
        caselog.step("Check the logo opened the About page")
        ui.expect(ui.expect_screen("about"), "the crown logo did not open About")
        c.shot(ui.shoot("AboutFromLogo"))
        c.note("the crown logo opened About")
    ui.back()
    ui.expect(ui.on_menu(6.0), "About back did not return to the main menu")
    print("PASS: About — menu item and crown logo both open it, links present, FAQ "
          "stays in the app and scrolls to submit feedback")


if __name__ == "__main__":
    fc.main(run)
