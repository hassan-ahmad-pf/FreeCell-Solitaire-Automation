#!/usr/bin/env python3
"""verifyMoreGamesBtn: the in-app More Games page.

MG-01  the gift icon opens the in-app promo page (no App Store)
MG-02  one swipe scrolls the list to Card Games and Spiderette
MG-03  Back returns to the main menu

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyMoreGamesBtn.py
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

# The promo list below the pinned "back" header, in px.
BAND = (0, 335, 1290, 2712)
# A real swipe changes about a quarter of the list; the animated smileys alone
# change well under 1%.
MOVED = 0.05


def run() -> None:
    fc.menu()
    with caselog.case("MG-01") as c:
        ui.expect(ui.tap("more_games", settle=2.5), "More Games control not found on the menu")
        ui.expect(helpers.in_app(), f"More Games left FreeCell for {helpers.active_app()}")
        ui.expect(ui.expect_screen("more_games"), "More Games did not open its page")
        c.shot(ui.shoot("MoreGames"))
        c.note("in-app promo page opened")
    with caselog.case("MG-02") as c:
        top = ui.shoot("_mg_top")
        ui.scroll(True)
        ui.settle(4.0)
        bottom = c.shot(ui.shoot("MoreGamesScrolled"))
        moved = fc.diff_frac(top, bottom, BAND)
        ui.expect(moved >= MOVED, f"the More Games page did not scroll — one swipe changed "
                                  f"only {moved:.1%} of the list")
        ui.expect(ui.is_on("mg_header"), "scrolling More Games navigated away from it")
        missing = [name for name in ("mg_cardgames", "mg_spiderette") if not ui.is_on(name)]
        ui.expect(not missing, f"after one swipe the page does not show {missing}")
        c.note(f"one swipe moved {moved:.0%} of the list — Card Games and Spiderette in view")
    with caselog.case("MG-03") as c:
        ui.back()
        ui.expect(ui.on_menu(6.0), "More Games back did not return to the main menu")
        c.note("back on the main menu")
    print("PASS: More Games opened in the app, swiped to Card Games and Spiderette, "
          "and returned")


if __name__ == "__main__":
    fc.main(run)
