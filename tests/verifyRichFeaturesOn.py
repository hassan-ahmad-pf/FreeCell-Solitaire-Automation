#!/usr/bin/env python3
"""Rich Features ON: the Options switch reads ON and the Easy table draws the HUD.

Main menu → Options → scroll to Rich Features and read the switch. Turn it
on only when it is off (on is the default), and require it to read ON.
Back to the menu → Play → Easy. The timer, the score, the multiplier and
the move counter beside "menu" must all be drawn.
"""
from __future__ import annotations

import sys

import freecell_ui as ui

NAME = "opt_rich_features"
TITLE = "Rich Features"


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")
    ui.expect(ui.open_options(), "Options did not open from the main menu")
    start = ui.option_state(NAME)
    ui.expect(start is not None, "Rich Features row not found on Options")
    print(f"  Rich Features reads {'ON' if start else 'OFF'} on Options at the start",
          flush=True)
    option = ui.switch_to(NAME, True, TITLE, "RichFeaturesOptionOn")
    ui.back()
    ui.expect(ui.on_menu(6.0), "back from Options did not reach the main menu")
    ui.expect(ui.start_game("easy"), "Easy did not reach the table")
    ui.start_deal()
    ui.expect(ui.at_table(), "not on the gameplay screen")
    table = ui.settled_shot("RichFeaturesOn")
    ink = ui.hud_ink(table)
    missing = [name for name in ui.HUD_ITEMS if ink[name] < ui.HUD_SEEN]
    ui.expect(
        not missing,
        f"Rich Features is ON but the table does not draw: {', '.join(missing)} "
        f"(ink {ink}) — {table}",
    )
    ui.expect(ui.to_menu(), "could not return to the menu after the table")
    print(f"PASS: Rich Features ON — timer, score, multiplier and moves are "
          f"drawn (ink {ink}) — {option}, {table}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
