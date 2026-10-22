#!/usr/bin/env python3
"""verifyMoreGamesIcons: the promo strip on the menu. [ONLINE]

After a won game FreeCell draws a strip of five other-game icons on the
left of the menu, above More Games. FreeCell publishes them as buttons
("iconette <code> x13"), so presence and taps go through the accessibility
tree rather than pixels.

PI-01  all five icons are on the menu
PI-02  Solitaire   → App Store "Solitaire: Classic Cards", back on the menu
PI-03  Sudoku 2    → App Store "Sudoku …", back on the menu
PI-04  Card Games  → App Store "Card Games", back on the menu
PI-05  Spider      → App Store "Spider Solitaire", back on the menu
PI-06  Spiderette  → App Store "… Spiderette", back on the menu

The page name is read from the App Store's own tree. It must carry its
icon's name AND none of the other four names — three titles
contain "Solitaire" — so a swapped link cannot pass. Coming back is the
status-bar crumb (or a plain foreground), never a kill.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyMoreGamesIcons.py
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

# (case, icon button, what the strip shows, App Store name it must carry)
ICONS = (
    ("PI-02", "iconette kln x13", "Solitaire", "Solitaire: Classic Cards"),
    ("PI-03", "iconette sdo x13", "Sudoku 2", "Sudoku"),
    ("PI-04", "iconette cgs x13", "Card Games", "Card Games"),
    ("PI-05", "iconette spr x13", "Spider", "Spider Solitaire"),
    ("PI-06", "iconette spe x13", "Spiderette", "Spiderette"),
)
STRIP_WAIT = 10.0


def _icon_rect(button: str) -> dict | None:
    eid = fc.named("Button", button)
    if not eid or fc.attr(eid, "visible") is not True:
        return None
    r = fc.rect(eid)
    return r if r and r.get("width", 0) > 0 else None


def _store_name_ok(title: str, expected: str) -> str:
    """'' when *title* is the page for *expected* only; otherwise why not."""
    low = title.lower()
    if expected.lower() not in low:
        return f"the page is {title!r}, not {expected!r}"
    others = [e for _c, _b, _l, e in ICONS if e != expected and e.lower() in low]
    if others:
        return f"the page {title!r} also matches {others}, so it does not identify one game"
    return ""


def run() -> None:
    fc.go_online()
    fc.menu()

    with caselog.case("PI-01") as c:
        deadline = time.time() + STRIP_WAIT
        missing = [label for _c, button, label, _e in ICONS if not _icon_rect(button)]
        while missing and time.time() < deadline:
            time.sleep(1.0)
            missing = [label for _c, button, label, _e in ICONS if not _icon_rect(button)]
        c.shot(ui.shoot("more_games_icons"))
        ui.expect(not missing, f"{len(missing)}/{len(ICONS)} promo icons are not on the "
                               f"menu: {missing}. The strip is drawn only after a won "
                               "game — verifyVictory wins one first.")
        c.note("Spider, Solitaire, Sudoku 2, Card Games, Spiderette on the menu")

    for cid, button, label, expected in ICONS:
        with caselog.case(cid) as c:
            r = _icon_rect(button)
            ui.expect(r, f"the {label} icon is no longer on the menu")
            fc.tap_rect(r, settle=3.0)
            went = fc.left_app()
            ui.expect(went == fc.APP_STORE,
                      f"the {label} icon did not open the App Store — in front: "
                      f"{went or 'unknown'}")
            title = fc.store_title()
            c.shot(ui.shoot(f"promo_store_{label.lower().replace(' ', '_')}"))
            ui.expect(title, f"the App Store page for {label} never rendered a title")
            why = _store_name_ok(title, expected)
            ui.expect(not why, f"the {label} icon opened the wrong page: {why}")
            ui.expect(fc.tap_back_to_app() or fc.resume(),
                      f"could not switch back to FreeCell from {label}'s store page")
            ui.expect(ui.on_menu(10.0),
                      f"came back from {label}'s store page, but not to the main menu")
            c.note(f"App Store: {title}; back on the menu")

    print("PASS: the five promo icons are on the menu and each opens its own App "
          "Store page")


if __name__ == "__main__":
    fc.main(run)
