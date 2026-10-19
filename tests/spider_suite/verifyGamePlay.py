#!/usr/bin/env python3
"""Spider's verifyGamePlay on FreeCell: the table plays.

GP-01  Back, menu, tap to undo, tap to lower and tap for hints are on screen
GP-12  untouched for 10 s the deal's timer stays 0:00 under "tap a card to
       start"; a card tapped up to its foundation starts it
GP-25  that card going up makes the score count
GP-03  a card move is undone exactly (FreeCell has no stock deal)
GP-04  tap to lower drops the playfield
GP-05  tap to raise brings it back
GP-06  tap for hints shows a hint ("tap for more")
GP-07  the in-game menu shows replay, abandon, options, new, help and FAQ
GP-10  Rich Features OFF hides the timer, score and multiplier
GP-11  Rich Features ON brings them back
GP-14  New deals a different board

Board checks read the exact layout from the accessibility tree; the
playfield's height is its foundation row's y.

Run:  ./.venv/bin/python -u tests/spider_suite/verifyGamePlay.py
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
import helpers  # noqa: E402

UNDO = (220, 2280)
# Free cells, foundations and columns in px, raised or lowered.
PLAYFIELD = (0, 560, 1290, 1700)
# A hint ghosts a card across the columns (~4% of the playfield); an idle
# table changes nothing.
HINT_SHOWN = 0.01
LOWER = ((645, 2150), (645, 2250))
SHIFT = 15.0
CONTROLS = ("back_game", "table_menu", "hint_undo", "hint_hints")
DRAWER = ("drawer_replay", "drawer_abandon", "drawer_options", "drawer_new",
          "drawer_help", "drawer_faq")
RICH = "opt_rich_features"
RICH_TITLE = "Rich Features"
NEW_DEAL = 10
IDLE = 10.0
TIMER_RUN = 2.0
TAP_TO_START = "tap a card to start"


def _top_y() -> float:
    b = fc.settled_board()
    ui.expect(b is not None, "could not read the board")
    return b.top_y


def _toggle_lower(start: float) -> float:
    """Tap the lower / raise control; the playfield's new top."""
    for point in LOWER:
        helpers.wda_tap(point, settle=2.5)
        now = _top_y()
        if abs(now - start) > SHIFT:
            return now
    return start


def run() -> None:
    fc.menu()
    ui.expect(ui.tap("menu_play", settle=2.0), "Play control not found on the menu")
    ui.expect(ui.wait_for("difficulty_easy", timeout=6.0), "Play did not open the picker")
    ui.expect(ui.tap("difficulty_easy", settle=2.0), "Easy could not be tapped")
    ui.answer_prompt("abandon", "Yes")
    ui.expect(ui.at_table(), "Easy did not reach the table")

    with caselog.case("GP-01") as c:
        missing = [name for name in CONTROLS if not ui.is_on(name)]
        lowered = ui.is_on("back_game") and ui.find("back_game")[1] > 400
        if not (ui.is_on("hint_lower") or lowered):
            missing.append("hint_lower")
        c.shot(ui.shoot("GamePlayTable"))
        ui.expect(not missing, f"the table is missing {missing}")
        c.note("back, menu, undo, lower and hints all on screen")
    ui.await_rules_prompt()

    with caselog.case("GP-12") as c:
        time.sleep(IDLE)
        idle = c.shot(ui.shoot("GamePlayIdle"))
        timer0, score0 = fc.hud(idle)
        footer = fc.table_footer(idle)
        ui.expect(timer0 == 0, f"the timer reads {fc.mmss(timer0)} after {IDLE:.0f}s on a new "
                               f"deal without a move (see {idle})")
        ui.expect(any(TAP_TO_START in line.lower() for line in footer),
                  f"the footer reads {footer}, not '{TAP_TO_START}' (see {idle})")
        _before, _after, card = fc.play_to_foundation()
        time.sleep(TIMER_RUN)
        moved, timer1, score1 = fc.hud_after_move("GamePlayCardUp")
        c.shot(moved)
        ui.expect(timer1 is not None and timer1 > 0,
                  f"the timer did not start: 0:00 before {card} went up, {fc.mmss(timer1)} "
                  f"after (see {moved})")
        c.note(f"{IDLE:.0f}s untouched: 0:00 under '{TAP_TO_START}'; {card} tapped up to its "
               f"foundation: timer 0:00 → {fc.mmss(timer1)}")
    with caselog.case("GP-25") as c:
        c.shot(moved)
        ui.expect(score1 is not None and score1 > (score0 or 0),
                  f"the score did not count {card} going up to its foundation: "
                  f"{score0 or 0:,} before, {'unreadable' if score1 is None else f'{score1:,}'} "
                  f"after (see {moved})")
        c.note(f"{card} went up to its foundation: score {score0 or 0:,} → {score1:,}")

    with caselog.case("GP-03") as c:
        before, after, card = fc.play_one_move()
        c.shot(ui.shoot("GamePlayMoved"))
        helpers.wda_tap(UNDO, settle=1.5)
        undone = fc.settled_board()
        c.shot(ui.shoot("GamePlayUndone"))
        ui.expect(undone == before, f"undo did not restore the board after moving {card}: "
                                    f"{before.moved(undone) if undone else 'unreadable'}")
        c.note(f"moved {card}, undo restored every card")

    with caselog.case("GP-04") as c:
        start = _top_y()
        now = _toggle_lower(start)
        if now < start - SHIFT:
            print("  the playfield was lowered already — raised it first", flush=True)
            start = now
            now = _toggle_lower(start)
        c.shot(ui.shoot("GamePlayLowered"))
        ui.expect(now > start + SHIFT, f"tap to lower did not drop the playfield "
                                       f"(top {start:.0f} -> {now:.0f} pt)")
        c.note(f"top {start:.0f} -> {now:.0f} pt")
    with caselog.case("GP-05") as c:
        back = _toggle_lower(now)
        c.shot(ui.shoot("GamePlayRaised"))
        ui.expect(abs(back - start) <= SHIFT / 3,
                  f"tap to raise did not bring the playfield back ({now:.0f} -> {back:.0f}, "
                  f"started at {start:.0f} pt)")
        c.note(f"top {now:.0f} -> {back:.0f} pt")

    with caselog.case("GP-06") as c:
        before = ui.shoot("_hint_before")
        deck = ui.find("hint_deck")
        ui.expect(deck, "the hint deck (bottom right) is not on the table")
        helpers.tap(deck, settle=0.8)
        after = c.shot(ui.shoot("GamePlayHint"))
        more = ui.is_on("hint_more")
        moved = fc.diff_frac(before, after, PLAYFIELD)
        ui.expect(more or moved >= HINT_SHOWN,
                  f"tap for hints showed no hint ({moved:.1%} of the playfield changed)")
        c.note(f"hint shown — {'tap for more, ' if more else ''}{moved:.1%} of the playfield "
               "highlighted")

    with caselog.case("GP-07") as c:
        ui.expect(ui.open_table_drawer(), "the in-game menu did not open")
        missing = [name for name in DRAWER if not ui.is_on(name)]
        c.shot(ui.shoot("GamePlayDrawer"))
        ui.expect(not missing, f"the in-game menu is missing {missing}")
        ui.close_drawer()
        c.note("replay, abandon, options, new, help, FAQ")

    touched = False
    try:
        with caselog.case("GP-10") as c:
            on_shot = ui.settled_shot("RichFeaturesTableOn")
            on_ink = ui.hud_ink(on_shot)
            absent = [name for name in ui.HUD_ITEMS if on_ink[name] < ui.HUD_SEEN]
            ui.expect(not absent, f"Rich Features ON does not draw {absent} ({on_ink})")
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(RICH, True, RICH_TITLE, "opened from the table")
            touched = True
            c.shot(ui.switch_to(RICH, False, RICH_TITLE, "RichFeaturesOptionOff"))
            off_shot = c.shot(ui.back_to_table_shot("RichFeaturesOff"))
            off_ink = ui.hud_ink(off_shot)
            still = [name for name in ui.HUD_ITEMS if off_ink[name] > ui.HUD_GONE]
            ui.expect(not still, f"Rich Features OFF still draws {still} ({off_ink})")
            c.note("timer, score, multiplier and moves hidden")
        with caselog.case("GP-11") as c:
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(RICH, False, RICH_TITLE, "opened from the table")
            ui.switch_to(RICH, True, RICH_TITLE, "RichFeaturesOptionBackOn")
            touched = False
            again_shot = c.shot(ui.back_to_table_shot("RichFeaturesBackOn"))
            again_ink = ui.hud_ink(again_shot)
            gone = [name for name in ui.HUD_ITEMS if again_ink[name] < ui.HUD_SEEN]
            ui.expect(not gone, f"Rich Features ON did not bring back {gone} ({again_ink})")
            c.note("timer, score, multiplier and moves back")
    finally:
        if touched:
            ui.restore_rich_features()

    with caselog.case("GP-14") as c:
        before = fc.settled_board()
        ui.expect(ui.open_table_drawer(), "the in-game menu did not open for New")
        ui.expect(ui.tap("drawer_new", settle=2.0), "New could not be tapped")
        if fc.wait_alert("abandon", timeout=2.0):
            helpers.answer_alert("Yes", settle=1.5)
        ui.settle_prompts()
        ui.expect(ui.at_table(timeout=8.0), "New did not leave a game table")
        after = fc.settled_board()
        c.shot(ui.shoot("GamePlayNew"))
        ui.expect(before is not None and after is not None, "could not read the boards")
        moved = len(before.moved(after))
        ui.expect(moved >= NEW_DEAL, f"New left the same deal ({moved} cards moved)")
        c.note(f"a different deal ({moved} of 52 cards elsewhere)")

    ui.expect(ui.to_menu(), "could not return to the menu after the table")
    print("PASS: the table plays — controls, timer and score, undo, lower / raise, hints, "
          "drawer, Rich Features both ways, and New")


if __name__ == "__main__":
    fc.main(run)
