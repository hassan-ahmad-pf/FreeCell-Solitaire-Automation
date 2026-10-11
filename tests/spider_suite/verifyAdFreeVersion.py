#!/usr/bin/env python3
"""Spider's verifyAdFreeVersion on FreeCell: About's "ad free version" link. [ONLINE]

AF-02  the link asks No / Yes before the store, FreeCell still in front
AF-01  No closes the question and leaves FreeCell on About
AF-03  Yes opens the App Store on FreeCell's paid build
AF-04  the status-bar crumb resumes FreeCell (it kept running behind the store)

FreeCell asks with a native alert, so its text and buttons are read through
WDA rather than found by shape. Which app came up is the foreground bundle
id; which product it shows is the App Store page title.

FreeCell returns to its main menu whenever it comes back from the
background (About -> Home -> reopen does the same, with the process alive
throughout), so AF-04 proves "resumed, not restarted" from the process
state instead of from About being on screen.

Run:  ./.venv/bin/python -u tests/spider_suite/verifyAdFreeVersion.py
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

LINK = "about_adfree"
PHRASE = "ad free version"
EXPECTED_TITLE = "FreeCell Solitaire +"


def _squash(text: str) -> str:
    return "".join(text.lower().split())


def _ask() -> list[str]:
    ui.expect(ui.tap(LINK, settle=2.5), "the 'ad free version' link could not be tapped")
    text = fc.wait_alert(PHRASE, timeout=6.0)
    ui.expect(text, "tapping 'ad free version' did not ask about the ad-free version "
                    f"(alert on screen: {helpers.alert_text()!r})")
    return helpers.alert_buttons()


def run() -> None:
    fc.go_online()
    fc.menu()
    ui.expect(ui.tap("menu_about", settle=2.5), "About control not found on the menu")
    ui.expect(ui.expect_screen("about"), "tapping About did not open About")
    ui.expect(ui.is_on(LINK), "the 'ad free version' link is not on About")

    with caselog.case("AF-02") as c:
        buttons = _ask()
        c.shot(ui.shoot("AdFreeVersionAsk"))
        ui.expect(buttons == ["No", "Yes"],
                  f"the ad-free question should offer No then Yes, got {buttons}")
        ui.expect(helpers.in_app(), "the ad-free question opened outside FreeCell")
        c.note("asks No / Yes, FreeCell still in front")

    with caselog.case("AF-01") as c:
        ui.expect(helpers.answer_alert("No", settle=2.0), "could not press No")
        ui.expect(not helpers.alert_text(), "the question stayed up after No")
        ui.expect(helpers.in_app(), f"No left FreeCell for {helpers.active_app()}")
        ui.expect(ui.expect_screen("about", timeout=5.0), "No did not leave About on screen")
        c.shot(ui.shoot("AdFreeVersionNo"))
        c.note("No kept FreeCell on About")

    with caselog.case("AF-03") as c:
        buttons = _ask()
        ui.expect(buttons == ["No", "Yes"],
                  f"the second ad-free question should offer No then Yes, got {buttons}")
        ui.expect(helpers.answer_alert("Yes", settle=4.0), "could not press Yes")
        went = fc.left_app(timeout=12.0)
        ui.expect(went == fc.APP_STORE, f"Yes did not open the App Store — in {went}")
        title = fc.store_title()
        shot = c.shot(ui.shoot("AdFreeVersion"))
        ui.expect(_squash(EXPECTED_TITLE) in _squash(title),
                  f"the App Store opened on {title!r}, not {EXPECTED_TITLE!r} (see {shot})")
        c.note(f"App Store page {title!r}")

    with caselog.case("AF-04") as c:
        state = helpers.app_state()
        ui.expect(state in (2, 3),
                  f"FreeCell was not left running behind the App Store (state {state}) "
                  "— coming back would be a restart")
        ui.expect(fc.tap_back_to_app(), "the status-bar crumb did not bring FreeCell back")
        landed = ("About" if ui.expect_screen("about", timeout=6.0)
                  else "the main menu" if ui.on_menu(6.0) else "")
        c.shot(ui.shoot("AdFreeVersionBack"))
        ui.expect(landed, "came back from the App Store but not to About or the main menu")
        c.note(f"FreeCell kept running behind the store; the crumb resumed it on {landed}")

    ui.expect(ui.to_menu(), "could not return to the main menu after About")
    print("PASS: 'ad free version' asks first, No stays on About, Yes opens "
          f"{EXPECTED_TITLE!r}, and the crumb resumes FreeCell")


if __name__ == "__main__":
    fc.main(run)
