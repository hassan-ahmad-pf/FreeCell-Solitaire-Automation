#!/usr/bin/env python3
"""verifyHelpShift: Contact Us leaves Options offline.

HS-02  with Airplane Mode on and Wi-Fi off, Contact Us still leaves Options
       (the page shows no connection; the redirect is what is checked)

The no-network page's "close icon" returns to Options. Run after
verifyOptions, it carries on from the Options page that test leaves open.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyHelpShift.py
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

SUPPORT_X = (30, 85)   # points


def run() -> None:
    fc.go_offline()
    if not ui.expect_screen("options", timeout=1.0):
        fc.menu()
    ui.expect(ui.open_options(), "Options did not open from the main menu")
    if not ui.is_on("contact_us"):
        fc.options_top()
    ui.expect(ui.is_on("contact_us"), "Contact Us is missing from Options")
    with caselog.case("HS-02") as c:
        ui.expect(ui.tap("contact_us", settle=4.0), "Contact Us could not be tapped")
        time.sleep(1.0)
        shot = c.shot(ui.shoot("HelpShift"))
        caselog.step("Check Contact Us left Options for the support page")
        ui.expect(not ui.is_on("screen_options"),
                  f"Contact Us did not leave Options (see {shot})")
        c.note("left Options for the no-network support page")

    if not fc.tap_named("Button", "close icon", settle=2.0):
        caselog.step("Tap the X at the top left of the support page")
        fc.tap_point(*SUPPORT_X, settle=2.0)
    ui.expect(ui.expect_screen("options", timeout=8.0),
              "closing the support page did not return to Options")
    ui.back()
    ui.expect(ui.on_menu(8.0), "Options back did not return to the main menu")
    print("PASS: Contact Us left Options offline; closing it returned to the menu")


if __name__ == "__main__":
    fc.main(run)
