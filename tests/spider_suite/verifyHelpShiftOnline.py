#!/usr/bin/env python3
"""Spider's verifyHelpShiftOnline on FreeCell: Contact Us loads support. [ONLINE]

HS-01  Options → Contact Us leaves Options and PeopleFun Support loads

Then the page's X (top left, not named in the tree) returns to Options and
Options' back returns to the main menu.

Run:  ./.venv/bin/python -u tests/spider_suite/verifyHelpShiftOnline.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

SUPPORT_X = (30, 85)   # points


def run() -> None:
    fc.go_online()
    fc.menu()
    ui.expect(ui.open_options(), "Options did not open from the main menu")
    ui.expect(ui.is_on("contact_us"), "Contact Us is missing from Options")
    ui.expect(ui.tap("contact_us", settle=4.0), "Contact Us could not be tapped")

    with caselog.case("HS-01") as c:
        title = fc.support_title(timeout=24.0)
        shot = c.shot(ui.shoot("HelpShiftOnline"))
        ui.expect(not ui.is_on("screen_options"),
                  f"Contact Us did not leave Options (see {shot})")
        ui.expect(title, f"Contact Us left Options but PeopleFun Support did not load "
                         f"(see {shot})")
        c.note(f"opened {title}")

    fc.tap_point(*SUPPORT_X, settle=2.5)
    ui.expect(ui.expect_screen("options", timeout=8.0),
              "the PeopleFun Support X did not return to Options")
    ui.back()
    ui.expect(ui.on_menu(8.0), "Options back did not return to the main menu")
    print(f"PASS: Contact Us opened {title}; its X and Options back returned "
          "to the main menu")


if __name__ == "__main__":
    fc.main(run)
