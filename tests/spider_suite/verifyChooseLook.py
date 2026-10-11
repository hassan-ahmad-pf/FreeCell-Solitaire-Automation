#!/usr/bin/env python3
"""Spider's verifyChooseLook on FreeCell: the look picker reaches the table.

CL-01  Choose Look opens on Surface
CL-03  Cards and Surface tabs switch
CL-04  the 6th surface is selected and the table felt matches it
CL-05  the 5th card back is selected and the table's backs match it

Both palettes are picked, then one Easy deal checks both on the table.
Surface 1 / Cards 1 are put back from a finally: later crops bake them.
Runs offline: entering a game online can raise a live interstitial.

Run:  ./.venv/bin/python -u tests/spider_suite/verifyChooseLook.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402

SURFACE_N = 6
CARDS_N = 5
CHANGE_TOL = 0.10
MATCH_FELT = 0.10
MATCH_CARDS = 0.18
# Half-size of a palette and its white frame, in pixels: (dx, dy).
FRAME = {"surface": (170, 85), "cards": (115, 115)}
SWATCH = {"surface": (120, 35), "cards": (28, 28)}
FRAMED = 0.04
CLEAR_BAND = (0.55, 0.60)


def _box(tab: str, n: int, half) -> tuple[int, int, int, int]:
    cx, cy = ui.look_centres(tab)[n - 1]
    dx, dy = half
    return cx - dx, cy - dy, cx + dx, cy + dy


def _swatch(img, tab: str, n: int):
    x0, y0, x1, y1 = _box(tab, n, SWATCH[tab])
    return ui._patch(img, y0, y1, x0, x1)


def _pick(tab: str, n: int):
    """(default colour, picked colour) after tapping palette *n* on *tab*.

    The white frame must move: palette *n* gains it and palette 1 loses it.
    """
    before_path = ui.shoot(f"ChooseLook_{tab}_before")
    before = ui.screen_rgb(before_path)
    default, picked = _swatch(before, tab, 1), _swatch(before, tab, n)
    ui.look_pick(tab, n)
    after_path = ui.shoot(f"ChooseLook_{tab}_{n}")
    gained = fc.diff_frac(before_path, after_path, _box(tab, n, FRAME[tab]))
    lost = fc.diff_frac(before_path, after_path, _box(tab, 1, FRAME[tab]))
    ui.expect(gained >= FRAMED and lost >= FRAMED,
              f"tapping {tab} palette {n} did not move the white frame to it "
              f"(palette {n} changed {gained:.1%}, palette 1 {lost:.1%}; see {after_path})")
    return default, picked


def _felt(img):
    """Table felt colour; a patterned surface is averaged over a clear band."""
    flat = ui.felt_colour(img)
    if flat is not None:
        return flat
    h, w = img.shape[:2]
    return ui._patch(img, int(h * CLEAR_BAND[0]), int(h * CLEAR_BAND[1]),
                     int(w * 0.12), int(w * 0.88))


def run() -> None:
    fc.go_offline()
    fc.menu()

    with caselog.case("CL-01") as c:
        ui.expect(ui.open_choose_look(), "Choose Look did not open")
        ui.open_look_tab("surface")
        c.shot(ui.shoot("ChooseLookSurface"))
        ui.expect(ui.expect_screen("choose_look", timeout=5.0),
                  "Choose Look did not show the Surface tab")
        c.note("opened on Surface")

    with caselog.case("CL-03") as c:
        ui.open_look_tab("cards")
        c.shot(ui.shoot("ChooseLookCards"))
        ui.expect(ui.seen("screen_choose_look_cards", timeout=4.0),
                  "tapping Cards did not show the Cards tab")
        ui.open_look_tab("surface")
        ui.expect(ui.expect_screen("choose_look", timeout=4.0),
                  "tapping Surface did not bring the Surface tab back")
        c.note("Cards and Surface switched")

    restored = False
    table = None
    try:
        with caselog.case("CL-04") as c:
            old_felt, new_felt = _pick("surface", SURFACE_N)
            ui.open_look_tab("cards")
            old_backs, new_backs = _pick("cards", CARDS_N)
            ui.expect(ui.close_choose_look(), "Choose Look would not close")
            fc.enter_game("easy")
            table = c.shot(ui.settled_shot("ChooseLookTable"))
            felt = _felt(ui.screen_rgb(table))
            ui.expect(felt is not None, f"no clear patch of felt on the table (see {table})")
            change = ui.colour_dist(old_felt, felt)
            match = ui.colour_dist(felt, new_felt)
            ui.expect(change > CHANGE_TOL,
                      f"the felt did not change from Surface 1 ({change:.3f} apart)")
            ui.expect(match <= MATCH_FELT,
                      f"the felt {ui.colour_text(felt)} is not Surface {SURFACE_N} "
                      f"{ui.colour_text(new_felt)} ({match:.3f} apart, bar {MATCH_FELT})")
            c.note(f"felt matches Surface {SURFACE_N} ({match:.3f})")

        with caselog.case("CL-05") as c:
            c.shot(table)
            backs = ui.back_colour(ui.screen_rgb(table))
            ui.expect(backs is not None, f"could not read the card backs (see {table})")
            change = ui.colour_dist(old_backs, backs)
            match = ui.colour_dist(backs, new_backs)
            ui.expect(change > CHANGE_TOL,
                      f"the card backs did not change from Cards 1 ({change:.3f} apart)")
            ui.expect(match <= MATCH_CARDS,
                      f"the backs {ui.colour_text(backs)} are not Cards {CARDS_N} "
                      f"{ui.colour_text(new_backs)} ({match:.3f} apart, bar {MATCH_CARDS})")
            c.note(f"backs match Cards {CARDS_N} ({match:.3f})")
    finally:
        restored = ui.restore_default_look()

    ui.expect(restored, "the default look could not be put back")
    ui.expect(ui.to_menu(), "could not return to the menu after Choose Look")
    print(f"PASS: Choose Look — Surface {SURFACE_N} and Cards {CARDS_N} reached the "
          "table, and the default look is back")


if __name__ == "__main__":
    fc.main(run)
