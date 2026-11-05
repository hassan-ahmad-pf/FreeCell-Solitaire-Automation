#!/usr/bin/env python3
"""verifyOptions: named Options rows driven, then put back.

OP-01  Options opens from the main menu
OP-03  Applause Volume reaches 0%, 50% and 100%, one drag each
OP-04  Applause Volume keeps its position after leaving Options
OP-05  Auto Mute Sounds flips and flips back
OP-06  Card Lowering reaches 0%, 50% and 100%, one drag each

Values are read from the UISlider / UISwitch themselves. The starting values
are restored from a finally. It ends on Options, where verifyHelpShift
carries on with Contact Us.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyOptions.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

KEPT = 0.02


def _one_drag(name: str, target: float) -> float:
    """One drag to *target*. The case passes on that single move: FreeCell's
    sliders do not read back the position they were dragged to, and bisecting
    them walks the thumb back and forth."""
    value = fc.slider_drag(name, target)
    caselog.step(f"Check {name} moved to {target:.0%}")
    ui.expect(value is not None, f"{name} could not be read after one drag to {target:.0%}")
    return value


def run() -> None:
    fc.menu()
    with caselog.case("OP-01") as c:
        ui.expect(ui.open_options(), "Options did not open from the main menu")
        caselog.step("Check the Options page opened")
        ui.expect(not ui.on_menu(1.0), "the main menu is still showing")
        c.shot(ui.shoot("Options"))
        c.note("Options opened")

    applause = fc.slider_value("Applause Volume")
    mute = fc.switch_state("Auto Mute Sounds")
    lowering = None
    try:
        with caselog.case("OP-03") as c:
            got = [_one_drag("Applause Volume", t) for t in (0.0, 0.5, 1.0)]
            c.shot(ui.shoot("OptionsApplause"))
            c.note("0% → {:.0%}, 50% → {:.0%}, 100% → {:.0%} (one drag each)".format(*got))

        with caselog.case("OP-04") as c:
            kept = _one_drag("Applause Volume", 0.3)
            ui.back()
            ui.expect(ui.on_menu(6.0), "Options back did not reach the main menu")
            ui.expect(ui.open_options(), "Options did not open again")
            caselog.step(f"Check Applause Volume still reads {kept:.0%}")
            again = fc.slider_value("Applause Volume")
            ui.expect(again is not None and abs(again - kept) <= KEPT,
                      f"Applause Volume was {kept:.0%} and reads {again} after reopening")
            c.shot(ui.shoot("OptionsApplauseKept"))
            c.note(f"{kept:.0%} kept after leaving Options")

        with caselog.case("OP-05") as c:
            start = fc.switch_state("Auto Mute Sounds")
            ui.expect(start is not None, "Auto Mute Sounds could not be read")
            flipped = fc.switch_tap("Auto Mute Sounds")
            caselog.step(f"Check Auto Mute Sounds turned {'OFF' if start else 'ON'}")
            ui.expect(flipped == (not start), f"the first tap left Auto Mute Sounds {start}")
            back = fc.switch_tap("Auto Mute Sounds")
            caselog.step(f"Check Auto Mute Sounds is back {'ON' if start else 'OFF'}")
            ui.expect(back == start, f"the second tap did not return Auto Mute Sounds to {start}")
            c.shot(ui.shoot("OptionsAutoMute"))
            c.note(f"{'on' if start else 'off'} → {'on' if flipped else 'off'} → "
                   f"{'on' if back else 'off'}")

        with caselog.case("OP-06") as c:
            lowering = fc.slider_value("Card Lowering")
            if lowering is None:
                fc.control_rect("Slider", fc.SLIDERS["Card Lowering"])
                lowering = fc.slider_value("Card Lowering")
            got = [_one_drag("Card Lowering", t) for t in (0.0, 0.5, 1.0)]
            c.shot(ui.shoot("OptionsCardLowering"))
            c.note("0% → {:.0%}, 50% → {:.0%}, 100% → {:.0%} (one drag each)".format(*got))
    finally:
        caselog.step("Put the Options values back as they were before the test")
        if lowering is not None:
            fc.slider_drag("Card Lowering", lowering)
        if applause is not None:
            fc.slider_drag("Applause Volume", applause)
        if mute is not None:
            fc.switch_set("Auto Mute Sounds", mute)

    print("PASS: Options — Applause Volume and Card Lowering reach both ends and the "
          "middle, Applause is kept, Auto Mute flips both ways; values restored")


if __name__ == "__main__":
    fc.main(run)
