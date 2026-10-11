#!/usr/bin/env python3
"""Rank Strip: the switch reads ON and OFF, and the table follows it both ways.

Main menu → Options → scroll to Rank Strip and read the switch. Turn it on
only if it is off, and require it to read ON. Back → Play → Easy: that
table must draw the A…K strip (ON frame). Then, through the table's menu →
options, every run checks both directions on the same deal:

  reads ON  → tap → reads OFF → table without the strip (OFF frame)
  reads OFF → tap → reads ON  → table with the strip again

Each switch state is captured on Options (RankStripOption*.png) and the
three tables are side by side in log/RankStripCompare.png. If the case
stops half way, ``finally`` turns Rank Strip back ON (the default).
"""
from __future__ import annotations

import sys

import freecell_ui as ui

NAME = "opt_rank_strip"
TITLE = "Rank Strip"


def word(on: bool) -> str:
    return "ON" if on else "OFF"


def run() -> None:
    touched = False
    try:
        ui.expect(ui.launch_to_menu(), "could not reach the main menu")
        ui.expect(ui.open_options(), "Options did not open from the main menu")
        start = ui.option_state(NAME)
        ui.expect(start is not None, "Rank Strip row not found on Options")
        print(f"  Rank Strip reads {word(start)} on Options at the start", flush=True)
        ui.shoot("RankStripOptionStart")
        ui.switch_to(NAME, True, TITLE, "RankStripOptionOn")
        ui.back()
        ui.expect(ui.on_menu(6.0), "back from Options did not reach the main menu")
        ui.expect(ui.start_game("easy"), "Easy did not reach the table")
        ui.start_deal()
        ui.expect(ui.at_table(), "not on the gameplay screen")
        on_shot = ui.settled_shot("RankStripOn")
        on_ink = ui.rank_strip_ink(on_shot)
        ui.expect(on_ink >= ui.RANK_SEEN,
                  f"Rank Strip is ON but the table draws no strip "
                  f"(ink {on_ink}) — {on_shot}")

        ui.expect(ui.open_options(from_table=True),
                  "table menu → options did not open Options")
        ui.confirm_switch(NAME, True, TITLE, "opened from the table")
        touched = True
        ui.switch_to(NAME, False, TITLE, "RankStripOptionOff")
        off_shot = ui.back_to_table_shot("RankStripOff")
        off_ink = ui.rank_strip_ink(off_shot)
        off_changed = ui.band_changed(on_shot, off_shot, ui.RANK_STRIP)
        compare = ui.save_compare([(on_shot, True), (off_shot, False)],
                                  ui.rank_boxes, "RankStripCompare")
        ui.expect(off_changed >= ui.RANK_SEEN,
                  f"the table looks the same with Rank Strip ON and OFF "
                  f"({off_changed} px changed in the strip band) — {compare}")
        ui.expect(off_ink <= ui.RANK_GONE,
                  f"Rank Strip is OFF but the strip is still drawn "
                  f"(ON {on_ink}, OFF {off_ink}) — {compare}")

        ui.expect(ui.open_options(from_table=True),
                  "table menu → options did not open Options the second time")
        ui.confirm_switch(NAME, False, TITLE, "opened from the table")
        ui.switch_to(NAME, True, TITLE, "RankStripOptionBackOn")
        touched = False
        again_shot = ui.back_to_table_shot("RankStripBackOn")
        again_ink = ui.rank_strip_ink(again_shot)
        again_changed = ui.band_changed(off_shot, again_shot, ui.RANK_STRIP)
        compare = ui.save_compare(
            [(on_shot, True), (off_shot, False), (again_shot, True)],
            ui.rank_boxes, "RankStripCompare",
        )
        ui.expect(again_ink >= ui.RANK_SEEN and again_changed >= ui.RANK_SEEN,
                  f"Rank Strip is back ON but the strip did not come back "
                  f"(ink {again_ink}, {again_changed} px changed) — {compare}")
    finally:
        if touched:
            ui.restore_rank_strip()
    ui.expect(ui.to_menu(), "could not return to the menu after the table")
    print(f"PASS: Rank Strip started {word(start)}; ON draws the strip "
          f"({on_ink} px), OFF removes it ({off_ink} px), ON again brings it "
          f"back ({again_ink} px) — {compare}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
