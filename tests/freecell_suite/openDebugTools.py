#!/usr/bin/env python3
"""openDebugTools: the hidden QA unlock on About. [DEV]

FreeCell's QA entry point is About → the version line → 10 quick taps on the
crown emblem → the code typed on the keypad that opens. The code toggles QA.
With QA on, the menu carries the CONFIDENTIAL watermark and About gains a
"reset alerts" control in its bottom-right corner. Neither is in the
accessibility tree.

QA-02  QA is off before the unlock: no watermark, no "reset alerts" on About
QA-03  version line, 10 emblem taps and the code turn QA on
QA-04  the code again turns QA off

The run ends with QA on: verifyVictory and
verifyDifficultyLevels win games through its Synthetic Win panel.

Run:  ./.venv/bin/python -u tests/freecell_suite/openDebugTools.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import config  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402


def _about() -> None:
    if ui.expect_screen("about", timeout=0.8):
        return
    ui.expect(ui.tap("menu_about", settle=2.5), "About control not found on the menu")
    # Just after QA goes off the menu ignores taps for a few seconds.
    if not ui.expect_screen("about", timeout=5.0):
        ui.tap("menu_about", settle=2.5)
    ui.expect(ui.expect_screen("about", timeout=10.0),
              "tapping About did not open the About screen")


def _enter_code() -> None:
    """The gesture itself: version line, a rapid emblem burst, the code."""
    _about()
    ui.expect(ui.tap("about_version", settle=1.5),
              "the About screen has no version line to tap")
    point = ui.find("about_emblem")
    ui.expect(point, "the crown emblem is not on the About screen, so the QA "
                     "gesture has nothing to tap")
    caselog.step(f"Tap the crown emblem {config.QA_TAPS} times in quick succession")
    ui.expect(helpers.rapid_tap(point, times=config.QA_TAPS),
              "the tap burst could not be sent as one on-device action, so it "
              "was not a rapid gesture and this result is inconclusive")
    caselog.step("Type the QA code on the keypad that opened")
    ui.expect(helpers.type_keys(config.QA_CODE),
              "the QA code could not be typed — no keypad took the focus after "
              f"{config.QA_TAPS} emblem taps")


def _reset_alerts(timeout: float = 0.0):
    """Centre (px) of About's QA-only "reset alerts" control, or None."""
    if timeout and not ui.seen("about_reset_alerts", timeout=timeout):
        return None
    return ui.find("about_reset_alerts")


def _menu_after_code() -> None:
    if not ui.on_menu(2.0):
        ui.back(settle=2.0)
    ui.expect(ui.on_menu(6.0), "back from About did not return to the main menu")


def run() -> None:
    fc.menu()

    with caselog.case("QA-02") as c:
        if ui.is_on("qa_watermark"):
            print("  QA was already on — entering the code to turn it off first",
                  flush=True)
            _enter_code()
            _menu_after_code()
            ui.expect(not ui.seen("qa_watermark", timeout=3.0),
                      "entering the code again did not turn QA off — it is "
                      "supposed to toggle")
        caselog.step("Check the menu has no CONFIDENTIAL watermark and About has no "
                     "'reset alerts' control")
        ui.expect(not ui.is_on("qa_watermark"),
                  "the menu shows the CONFIDENTIAL watermark before the unlock")
        _about()
        ui.expect(not _reset_alerts(),
                  "About shows the QA 'reset alerts' control before the unlock — "
                  "it is supposed to stay hidden until QA is on")
        c.shot(ui.shoot("debug_tools_before"))
        c.note("no watermark on the menu, no 'reset alerts' on About")

    with caselog.case("QA-03") as c:
        _enter_code()
        _menu_after_code()
        caselog.step("Check the CONFIDENTIAL watermark now shows on the main menu")
        ui.expect(ui.seen("qa_watermark", timeout=6.0),
                  f"{config.QA_TAPS} emblem taps and the code did not put the "
                  "CONFIDENTIAL watermark on the menu")
        c.shot(ui.shoot("debug_tools_menu"))
        # About lays out its QA controls when it opens, so it is opened afresh.
        _about()
        caselog.step("Check About shows the 'reset alerts' control in its bottom-right corner")
        point = _reset_alerts(timeout=4.0)
        ui.expect(point, "QA is on (CONFIDENTIAL on the menu) but About has no "
                         "'reset alerts' control")
        ui.expect(point[0] > 1290 / 2 and point[1] > 2796 / 2,
                  f"'reset alerts' appeared at {point}, not in the bottom-right corner")
        c.shot(ui.shoot("debug_tools"))
        _menu_after_code()
        c.note(f"CONFIDENTIAL on the menu; 'reset alerts' bottom-right on About "
               f"({config.QA_TAPS} taps + code)")

    with caselog.case("QA-04") as c:
        _enter_code()
        _menu_after_code()
        caselog.step("Check the watermark and the 'reset alerts' control are gone")
        ui.expect(not ui.seen("qa_watermark", timeout=3.0),
                  "the code entered again left the CONFIDENTIAL watermark on the menu")
        _about()
        ui.expect(not _reset_alerts(),
                  "the code entered again left the 'reset alerts' control on About")
        c.shot(ui.shoot("debug_tools_off"))
        _menu_after_code()
        c.note("the code again: watermark and 'reset alerts' gone")

    caselog.step("Turn QA back on for the tests after this one")
    _enter_code()
    _menu_after_code()
    ui.expect(ui.seen("qa_watermark", timeout=6.0),
              "could not turn QA back on for verifyVictory")
    print("PASS: the hidden QA entry point is on About, and the code toggles it")


if __name__ == "__main__":
    fc.main(run)
