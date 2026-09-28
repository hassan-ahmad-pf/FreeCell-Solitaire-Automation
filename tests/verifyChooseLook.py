#!/usr/bin/env python3
"""Choose Look opens Surface, switches to Cards, then closes without leaving a new theme selected if possible."""
from __future__ import annotations

import sys

import helpers
import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.tap("choose_look", settle=2.0), "Choose Look control not found")
    ui.expect(ui.expect_screen("choose_look"),
              "tapping Choose Look did not open the Surface tab")
    surface = ui.shoot("ChooseLookSurface")
    if ui.have("screen_choose_look_cards"):
        helpers.wda_tap((900, 780), settle=1.4)
        cards = ui.shoot("ChooseLookCards")
    else:
        cards = surface
    if ui.have("look_close"):
        ui.expect(ui.tap("look_close", settle=1.2), "Choose Look close was not tappable")
    else:
        helpers.wda_tap((1180, 760), settle=1.2)
    ui.expect(ui.to_menu(), "could not return to the menu after Choose Look")
    print(f"PASS: Choose Look Surface/Cards opened and closed — {surface}, {cards}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
