#!/usr/bin/env python3
"""verifyOptions: named Options rows driven, then put back.

OP-01  Options opens from the main menu
OP-03  Applause Volume reaches min, max and the middle
OP-04  Applause Volume keeps its position after leaving Options
OP-05  Auto Mute Sounds flips and flips back
OP-06  Card Lowering reaches min, max and the middle

Values are read from the UISlider / UISwitch themselves. The starting values
are restored from a finally.

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

TOL = 0.04
KEPT = 0.02


def _ends_and_middle(name: str) -> list[float]:
    got = []
    for target in (0.0, 1.0, 0.5):
        value = fc.slider_set(name, target, tol=TOL)
        ui.expect(value is not None, f"{name} could not be read")
        ui.expect(abs(value - target) <= TOL,
                  f"{name} reads {value:.0%} after dragging to {target:.0%}")
        got.append(value)
    return got


def run() -> None:
    fc.menu()
    with caselog.case("OP-01") as c:
        ui.expect(ui.open_options(), "Options did not open from the main menu")
        ui.expect(not ui.on_menu(1.0), "the main menu is still showing")
        c.shot(ui.shoot("Options"))
        c.note("Options opened")

    applause = fc.slider_value("Applause Volume")
    mute = fc.switch_state("Auto Mute Sounds")
    lowering = None
    try:
        with caselog.case("OP-03") as c:
            got = _ends_and_middle("Applause Volume")
            c.shot(ui.shoot("OptionsApplause"))
            c.note("min {:.0%}, max {:.0%}, middle {:.0%}".format(*got))

        with caselog.case("OP-04") as c:
            kept = fc.slider_set("Applause Volume", 0.3, tol=TOL)
            ui.expect(kept is not None and abs(kept - 0.3) <= TOL,
                      f"Applause Volume did not move to 30% (reads {kept})")
            ui.back()
            ui.expect(ui.on_menu(6.0), "Options back did not reach the main menu")
            ui.expect(ui.open_options(), "Options did not open again")
            again = fc.slider_value("Applause Volume")
            ui.expect(again is not None and abs(again - kept) <= KEPT,
                      f"Applause Volume was {kept:.0%} and reads {again} after reopening")
            c.note(f"{kept:.0%} kept after leaving Options")

        with caselog.case("OP-05") as c:
            start = fc.switch_state("Auto Mute Sounds")
            ui.expect(start is not None, "Auto Mute Sounds could not be read")
            flipped = fc.switch_tap("Auto Mute Sounds")
            ui.expect(flipped == (not start), f"the first tap left Auto Mute Sounds {start}")
            back = fc.switch_tap("Auto Mute Sounds")
            ui.expect(back == start, f"the second tap did not return Auto Mute Sounds to {start}")
            c.note(f"{'on' if start else 'off'} → {'on' if flipped else 'off'} → "
                   f"{'on' if back else 'off'}")

        with caselog.case("OP-06") as c:
            lowering = fc.slider_value("Card Lowering")
            if lowering is None:
                fc.control_rect("Slider", fc.SLIDERS["Card Lowering"])
                lowering = fc.slider_value("Card Lowering")
            got = _ends_and_middle("Card Lowering")
            c.shot(ui.shoot("OptionsCardLowering"))
            c.note("min {:.0%}, max {:.0%}, middle {:.0%}".format(*got))
    finally:
        if lowering is not None:
            fc.slider_set("Card Lowering", lowering, tol=0.02)
        if applause is not None:
            fc.slider_set("Applause Volume", applause, tol=0.02)
        if mute is not None:
            fc.switch_set("Auto Mute Sounds", mute)

    ui.back()
    ui.expect(ui.on_menu(6.0), "Options back did not return to the main menu")
    print("PASS: Options — Applause Volume and Card Lowering reach both ends and the "
          "middle, Applause is kept, Auto Mute flips both ways; values restored")


if __name__ == "__main__":
    fc.main(run)
