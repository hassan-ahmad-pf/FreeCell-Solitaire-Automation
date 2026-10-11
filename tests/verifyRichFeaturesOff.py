#!/usr/bin/env python3
"""Rich Features OFF: the table HUD disappears, and comes back when it is ON again.

Main menu → Play → Easy. The timer, score, multiplier and the move counter
beside "menu" must be drawn — that frame is the ON reference. Then, through
the table's menu → options, both directions on the same deal:

  reads ON  → tap → reads OFF → all four gone
  reads OFF → tap → reads ON  → all four back

Each switch state is captured on Options (RichFeaturesOption*.png) and the
three tables are side by side in log/RichFeaturesCompare.png. If the case
stops half way, ``finally`` turns Rich Features back ON: it is the default,
and the ``tableau`` crop and the later cases expect the default table.
"""
from __future__ import annotations

import sys

import freecell_ui as ui

NAME = "opt_rich_features"
TITLE = "Rich Features"


def run() -> None:
    touched = False
    try:
        ui.expect(ui.launch_to_menu(), "could not reach the main menu")
        ui.expect(ui.start_game("easy"), "Easy did not reach the table")
        ui.start_deal()
        ui.expect(ui.at_table(), "not on the gameplay screen")
        on_shot = ui.settled_shot("RichFeaturesTableOn")
        on_ink = ui.hud_ink(on_shot)
        missing = [name for name in ui.HUD_ITEMS if on_ink[name] < ui.HUD_SEEN]
        ui.expect(
            not missing,
            f"the ON reference does not draw {', '.join(missing)} — is Rich "
            f"Features on? (ink {on_ink}) — {on_shot}",
        )

        ui.expect(ui.open_options(from_table=True),
                  "table menu → options did not open Options")
        ui.confirm_switch(NAME, True, TITLE, "opened from the table")
        touched = True
        option = ui.switch_to(NAME, False, TITLE, "RichFeaturesOptionOff")
        off_shot = ui.back_to_table_shot("RichFeaturesOff")
        off_ink = ui.hud_ink(off_shot)
        compare = ui.save_hud_compare(on_shot, off_shot)
        ui.expect(off_ink["moves"] >= 0,
                  f"the table 'menu' label is missing — cannot place the move "
                  f"counter — {off_shot}")
        still = [name for name in ui.HUD_ITEMS if off_ink[name] > ui.HUD_GONE]
        ui.expect(
            not still,
            f"Rich Features is OFF but the table still draws: {', '.join(still)} "
            f"(ON {on_ink}, OFF {off_ink}) — {compare}",
        )

        ui.expect(ui.open_options(from_table=True),
                  "table menu → options did not open Options the second time")
        ui.confirm_switch(NAME, False, TITLE, "opened from the table")
        ui.switch_to(NAME, True, TITLE, "RichFeaturesOptionBackOn")
        touched = False
        again_shot = ui.back_to_table_shot("RichFeaturesBackOn")
        again_ink = ui.hud_ink(again_shot)
        compare = ui.save_compare(
            [(on_shot, True), (off_shot, False), (again_shot, True)],
            ui.hud_boxes, "RichFeaturesCompare",
        )
        back = [name for name in ui.HUD_ITEMS if again_ink[name] < ui.HUD_SEEN]
        ui.expect(
            not back,
            f"Rich Features is back ON but these did not come back: "
            f"{', '.join(back)} (ink {again_ink}) — {compare}",
        )
    finally:
        if touched:
            ui.restore_rich_features()
    ui.expect(ui.to_menu(), "could not return to the menu after the table")
    print(f"PASS: Rich Features OFF hides timer, score, multiplier and moves, "
          f"ON brings them back (ON {on_ink}, OFF {off_ink}, ON again "
          f"{again_ink}) — {option}, {compare}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
