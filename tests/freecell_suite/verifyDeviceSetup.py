#!/usr/bin/env python3
"""verifyDeviceSetup: the phone is set up for an unattended run.

DS-01  Settings → Display & Brightness → Auto-Lock is Never. A phone that
       locks itself refuses every app launch after it (WDA answers 500), so
       one auto-lock used to fail the rest of the run
DS-02  Do Not Disturb is on (Control Center → Focus): no notification banner
       drops over a screen the suite is matching

Each case sets what it finds wrong, then reads it again: it passes when the
phone ends set up, and its note says what was changed. It runs first, before
FreeCell opens, and leaves the network as it was.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyDeviceSetup.py
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


def run() -> None:
    caselog.step("Check the phone is unlocked")
    ui.expect(helpers.wait_unlocked(), "the phone stayed locked")

    with caselog.case("DS-01", soft=True) as c:
        caselog.step("Open Settings → Display & Brightness and read Auto-Lock; set it to Never")
        ok, seen = helpers.auto_lock_never()
        ui.expect(ok, f"Auto-Lock is {seen or 'unreadable'}, not Never "
                      "(Low Power Mode holds it at 30 s)")
        c.note("Auto-Lock is Never")

    with caselog.case("DS-02", soft=True) as c:
        caselog.step("Look for Do Not Disturb's moon in the status bar")
        was_on = helpers.dnd_on()
        if not was_on:
            caselog.step("Turn Do Not Disturb on from Control Center → Focus")
        ui.expect(was_on or helpers.dnd_turn_on(),
                  "Do Not Disturb is off and Control Center → Focus did not turn it on")
        c.shot(ui.shoot("DeviceSetupDND"))
        c.note("Do Not Disturb is on" if was_on else "Do Not Disturb was off — turned it on")

    caselog.raise_if_failed()
    print("PASS: Auto-Lock is Never and Do Not Disturb is on")


if __name__ == "__main__":
    fc.main(run)
