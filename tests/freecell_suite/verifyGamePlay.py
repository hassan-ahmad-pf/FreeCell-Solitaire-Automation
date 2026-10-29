#!/usr/bin/env python3
"""verifyGamePlay: the table plays.

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
OP-10  Show Status Bar is ON by default and the iOS status bar shows on the
       table; OFF hides it and the table moves up; ON brings it back with the
       table where it started (switched from the table's Options)
OP-11  with the four free cells full, tapping a card that has nowhere to go
       flashes "this card cannot attach anywhere" (Show Card Messages is ON
       by default)
OP-12  with Show Card Messages OFF, tapping the same stuck card shows no
       note; the switch is then turned back ON
GP-14  New deals a different board (which also clears the full free cells)
OP-17  with Auto Hint at its default (OFF), nothing on the table moves in the
       15 s after a move
OP-18  with Auto Hint ON (switched from the table's Options), the table stays
       still for a few seconds after a move, then the next card to play
       pulses as the hint; tapping that card plays it; the switch is then
       turned back OFF
OP-15  on that deal a 13-card pile is built with legal moves; with the
       playfield lowered it no longer fits, so Maintain Card Spacing (ON by
       default) tucks its top cards away under an arrow; tapping the arrow
       spreads the whole pile out
OP-16  with Maintain Card Spacing OFF the same pile has no arrow and every
       card shows, squeezed closer; back ON the arrow returns, and the
       playfield is raised again

Board checks read the exact layout from the accessibility tree; the
playfield's height is its foundation row's y.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyGamePlay.py
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
STATUS = "opt_status_bar"
STATUS_TITLE = "Show Status Bar"
MESSAGES = "opt_card_messages"
MESSAGES_TITLE = "Show Card Messages"
NOTE = "this card cannot attach anywhere"
AUTO_HINT = "opt_auto_hint"
# Folds once the playfield is lowered (12 would; 15 raised).
PILE = 13
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
        caselog.step("Tap 'tap to lower / raise' under the cards")
        helpers.wda_tap(point, settle=2.5)
        now = _top_y()
        if abs(now - start) > SHIFT:
            return now
    return start


def _raise_back() -> None:
    """Raise the lowered playfield. Never raises — used from finally."""
    try:
        if ui.at_table(timeout=2.0):
            _toggle_lower(_top_y())
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not raise the playfield back ({exc})", flush=True)


def run() -> None:
    fc.menu()
    ui.expect(ui.tap("menu_play", settle=2.0), "Play control not found on the menu")
    ui.expect(ui.wait_for("difficulty_easy", timeout=6.0), "Play did not open the picker")
    ui.expect(ui.tap("difficulty_easy", settle=2.0), "Easy could not be tapped")
    ui.answer_prompt("abandon", "Yes")
    ui.expect(ui.at_table(), "Easy did not reach the table")

    with caselog.case("GP-01") as c:
        caselog.step("Check the table shows Back, menu, undo, lower / raise and hints")
        missing = [name for name in CONTROLS if not ui.is_on(name)]
        lowered = ui.is_on("back_game") and ui.find("back_game")[1] > 400
        if not (ui.is_on("hint_lower") or lowered):
            missing.append("hint_lower")
        c.shot(ui.shoot("GamePlayTable"))
        ui.expect(not missing, f"the table is missing {missing}")
        c.note("back, menu, undo, lower and hints all on screen")
    ui.await_rules_prompt()

    with caselog.case("GP-12") as c:
        caselog.step(f"Wait {IDLE:.0f} s without touching the cards")
        time.sleep(IDLE)
        idle = c.shot(ui.shoot("GamePlayIdle"))
        timer0, score0 = fc.hud(idle)
        footer = fc.table_footer(idle)
        caselog.step(f"Check the timer still reads 0:00 under '{TAP_TO_START}'")
        ui.expect(timer0 == 0, f"the timer reads {fc.mmss(timer0)} after {IDLE:.0f}s on a new "
                               f"deal without a move (see {idle})")
        ui.expect(any(TAP_TO_START in line.lower() for line in footer),
                  f"the footer reads {footer}, not '{TAP_TO_START}' (see {idle})")
        _before, _after, card = fc.play_to_foundation()
        caselog.step(f"Wait {TIMER_RUN:.0f} s for the timer to run")
        time.sleep(TIMER_RUN)
        moved, timer1, score1 = fc.hud_after_move("GamePlayCardUp")
        c.shot(moved)
        caselog.step("Check the timer has started")
        ui.expect(timer1 is not None and timer1 > 0,
                  f"the timer did not start: 0:00 before {card} went up, {fc.mmss(timer1)} "
                  f"after (see {moved})")
        c.note(f"{IDLE:.0f}s untouched: 0:00 under '{TAP_TO_START}'; {card} tapped up to its "
               f"foundation: timer 0:00 → {fc.mmss(timer1)}")
    with caselog.case("GP-25") as c:
        c.shot(moved)
        caselog.step(f"Check the score went up when {card} reached its foundation "
                     f"(it was {score0 or 0:,})")
        ui.expect(score1 is not None and score1 > (score0 or 0),
                  f"the score did not count {card} going up to its foundation: "
                  f"{score0 or 0:,} before, {'unreadable' if score1 is None else f'{score1:,}'} "
                  f"after (see {moved})")
        c.note(f"{card} went up to its foundation: score {score0 or 0:,} → {score1:,}")

    with caselog.case("GP-03") as c:
        before, after, card = fc.play_one_move()
        c.shot(ui.shoot("GamePlayMoved"))
        caselog.step("Tap 'tap to undo' under the cards")
        helpers.wda_tap(UNDO, settle=1.5)
        undone = fc.settled_board()
        c.shot(ui.shoot("GamePlayUndone"))
        caselog.step(f"Check every card is back where it was before {card} moved")
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
        caselog.step("Check the cards moved down the screen")
        ui.expect(now > start + SHIFT, f"tap to lower did not drop the playfield "
                                       f"(top {start:.0f} -> {now:.0f} pt)")
        c.note(f"top {start:.0f} -> {now:.0f} pt")
    with caselog.case("GP-05") as c:
        back = _toggle_lower(now)
        c.shot(ui.shoot("GamePlayRaised"))
        caselog.step("Check the cards moved back up to where they started")
        ui.expect(abs(back - start) <= SHIFT / 3,
                  f"tap to raise did not bring the playfield back ({now:.0f} -> {back:.0f}, "
                  f"started at {start:.0f} pt)")
        c.note(f"top {now:.0f} -> {back:.0f} pt")

    with caselog.case("GP-06") as c:
        before = ui.shoot("_hint_before")
        deck = ui.find("hint_deck")
        ui.expect(deck, "the hint deck (bottom right) is not on the table")
        caselog.step("Tap 'tap for hints' (the hint deck, bottom right)")
        helpers.tap(deck, settle=0.8)
        after = c.shot(ui.shoot("GamePlayHint"))
        caselog.step("Check a hint is highlighted on the cards")
        more = ui.is_on("hint_more")
        moved = fc.diff_frac(before, after, PLAYFIELD)
        ui.expect(more or moved >= HINT_SHOWN,
                  f"tap for hints showed no hint ({moved:.1%} of the playfield changed)")
        c.note(f"hint shown — {'tap for more, ' if more else ''}{moved:.1%} of the playfield "
               "highlighted")

    with caselog.case("GP-07") as c:
        ui.expect(ui.open_table_drawer(), "the in-game menu did not open")
        caselog.step("Check the table menu lists Replay, Abandon, Options, New, Help and FAQ")
        missing = [name for name in DRAWER if not ui.is_on(name)]
        c.shot(ui.shoot("GamePlayDrawer"))
        ui.expect(not missing, f"the in-game menu is missing {missing}")
        ui.close_drawer()
        c.note("replay, abandon, options, new, help, FAQ")

    touched = False
    try:
        with caselog.case("GP-10") as c:
            caselog.step("Check the timer, score, multiplier and move count show on the table")
            on_shot = ui.settled_shot("RichFeaturesTableOn")
            on_ink = ui.hud_ink(on_shot)
            absent = [name for name in ui.HUD_ITEMS if on_ink[name] < ui.HUD_SEEN]
            ui.expect(not absent, f"Rich Features ON does not draw {absent} ({on_ink})")
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(RICH, True, RICH_TITLE, "opened from the table")
            touched = True
            c.shot(ui.switch_to(RICH, False, RICH_TITLE, "RichFeaturesOptionOff"))
            off_shot = c.shot(ui.back_to_table_shot("RichFeaturesOff"))
            caselog.step("Check the timer, score, multiplier and move count are hidden")
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
            caselog.step("Check the timer, score, multiplier and move count are back")
            again_ink = ui.hud_ink(again_shot)
            gone = [name for name in ui.HUD_ITEMS if again_ink[name] < ui.HUD_SEEN]
            ui.expect(not gone, f"Rich Features ON did not bring back {gone} ({again_ink})")
            c.note("timer, score, multiplier and moves back")
    finally:
        if touched:
            ui.restore_rich_features()

    bar_maybe_off = True
    try:
        with caselog.case("OP-10") as c:
            caselog.step("Check the iOS status bar (clock, battery) shows above the table")
            on_shot = c.shot(ui.settled_shot("StatusBarOn"))
            on_ink = ui.status_bar_ink(on_shot)
            ui.expect(on_ink >= ui.STATUS_SEEN,
                      f"no status bar above the table with Show Status Bar at its default "
                      f"({on_ink} white px, see {on_shot})")
            top_on = _top_y()
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(STATUS, True, STATUS_TITLE, "opened from the table — its default")
            c.shot(ui.switch_to(STATUS, False, STATUS_TITLE, "StatusBarOptionOff"))
            off_shot = c.shot(ui.back_to_table_shot("StatusBarOff"))
            caselog.step("Check the status bar is gone and the table moved up")
            off_ink = ui.status_bar_ink(off_shot)
            top_off = _top_y()
            ui.expect(off_ink <= ui.STATUS_GONE,
                      f"Show Status Bar OFF still shows the status bar ({off_ink} white px, "
                      f"see {off_shot})")
            ui.expect(top_off < top_on - SHIFT,
                      f"the table did not move up with the status bar hidden "
                      f"(top {top_on:.0f} -> {top_off:.0f} pt)")
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(STATUS, False, STATUS_TITLE, "opened from the table")
            ui.switch_to(STATUS, True, STATUS_TITLE, "StatusBarOptionBackOn")
            bar_maybe_off = False
            again_shot = c.shot(ui.back_to_table_shot("StatusBarBackOn"))
            caselog.step("Check the status bar is back and the table is where it started")
            again_ink = ui.status_bar_ink(again_shot)
            top_again = _top_y()
            ui.expect(again_ink >= ui.STATUS_SEEN,
                      f"Show Status Bar ON did not bring the status bar back ({again_ink} white "
                      f"px, see {again_shot})")
            ui.expect(abs(top_again - top_on) <= SHIFT / 3,
                      f"the table did not return to where it started "
                      f"(top {top_on:.0f} -> {top_off:.0f} -> {top_again:.0f} pt)")
            c.note(f"shown by default; OFF hid it and moved the table up {top_on - top_off:.0f} "
                   f"pt; ON brought it back with the table where it started")
    finally:
        if bar_maybe_off:
            ui.restore_status_bar()

    messages_maybe_off = True
    try:
        with caselog.case("OP-11") as c:
            b = fc.fill_free_cells()
            c.shot(ui.shoot("CardMessagesCellsFull"))
            stuck = next(iter(fc.homeless(b)), None)
            ui.expect(stuck, f"with the free cells full, every bottom card still has a move "
                             f"(board: {b.text()})")
            frames = fc.tap_and_watch(b, stuck, "CardMessageOn")
            caselog.step(f"Check {stuck} stayed put and '{NOTE}' showed")
            after = fc.settled_board()
            ui.expect(after == b, f"{stuck} moved, so it was not stuck "
                                  f"({b.moved(after) if after else 'board unreadable'})")
            seen = fc.card_message(frames)
            ui.expect(seen, f"no '{NOTE}' note in {len(frames)} frames over "
                            f"{frames[-1][0]:.1f} s after tapping {stuck} (first: {frames[0][1]})")
            c.shot(seen[1])
            c.note(f"free cells full; tapping {stuck} showed '{seen[2]}' {seen[0]:.1f} s "
                   f"after the tap")

        with caselog.case("OP-12") as c:
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(MESSAGES, True, MESSAGES_TITLE, "opened from the table — its default")
            c.shot(ui.switch_to(MESSAGES, False, MESSAGES_TITLE, "CardMessagesOptionOff"))
            ui.back_to_table_shot("CardMessagesOffTable")
            b = fc.settled_board()
            ui.expect(b is not None and fc.cells_used(b) >= 4,
                      "the table with the full free cells did not come back after Options")
            if stuck not in fc.homeless(b):
                stuck = next(iter(fc.homeless(b)), None)
                ui.expect(stuck, f"no stuck card left on the table (board: {b.text()})")
            frames = fc.tap_and_watch(b, stuck, "CardMessageOff")
            c.shot(frames[0][1])
            caselog.step(f"Check {stuck} stayed put and no '{NOTE}' note showed")
            after = fc.settled_board()
            ui.expect(after == b, f"{stuck} moved, so it was not stuck "
                                  f"({b.moved(after) if after else 'board unreadable'})")
            seen = fc.card_message(frames)
            if seen:
                at, path, text = seen
                ui.expect(False, f"Show Card Messages OFF still showed '{text}' {at:.1f} s after "
                                 f"tapping {stuck} (see {path})")
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(MESSAGES, False, MESSAGES_TITLE, "opened from the table")
            ui.switch_to(MESSAGES, True, MESSAGES_TITLE, "CardMessagesOptionBackOn")
            messages_maybe_off = False
            ui.back()
            ui.expect(ui.at_table(), "back from Options did not return to the table")
            c.note(f"OFF: tapping {stuck} showed no note in {len(frames)} frames over "
                   f"{frames[-1][0]:.1f} s; switched back ON")
    finally:
        if messages_maybe_off:
            ui.restore_card_messages()

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
        caselog.step("Check a different deal is on the table")
        ui.expect(before is not None and after is not None, "could not read the boards")
        moved = len(before.moved(after))
        ui.expect(moved >= NEW_DEAL, f"New left the same deal ({moved} cards moved)")
        c.note(f"a different deal ({moved} of 52 cards elsewhere)")

    hint_maybe_on = False
    try:
        with caselog.case("OP-17") as c:
            card, frames = fc.idle_after_move(after)
            idle = fc.idle_pulse(frames)
            c.shot(fc.save_png(idle.still, "AutoHintOff"))
            caselog.step(f"Check nothing on the table moved from {fc.HINT_LANDED:.0f} s to "
                         f"{idle.last:.0f} s after the tap")
            ui.expect(idle.start is None,
                      f"with {fc.AUTO_HINT} at its default (OFF) the table changed "
                      f"{idle.start or 0:.1f} s after tapping {card} ({idle.peak:.1%} of the "
                      f"playfield between two frames, at {idle.box})")
            c.note(f"tapped {card}; with {fc.AUTO_HINT} OFF nothing on the table moved from "
                   f"{fc.HINT_LANDED:.0f} to {idle.last:.0f} s after (at most {idle.peak:.2%} "
                   f"between frames)")

        with caselog.case("OP-18") as c:
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(AUTO_HINT, False, fc.AUTO_HINT, "opened from the table — its default")
            hint_maybe_on = True
            c.shot(ui.switch_to(AUTO_HINT, True, fc.AUTO_HINT, "AutoHintOptionOn"))
            ui.back()
            ui.expect(ui.at_table(), "back from Options did not return to the table")
            b = fc.settled_board()
            ui.expect(b is not None, "could not read the board")
            card, frames = fc.idle_after_move(b)
            idle = fc.idle_pulse(frames)
            caselog.step(f"Check the table stayed still for at least {fc.HINT_QUIET:.0f} s, "
                         "then a card pulsed as the hint")
            ui.expect(idle.start is not None,
                      f"with {fc.AUTO_HINT} ON no card pulsed in the {idle.last:.0f} s after "
                      f"tapping {card} (at most {idle.peak:.2%} of the playfield changed "
                      "between frames)")
            c.shot(fc.save_png(idle.popped, "AutoHintOn"))
            ui.expect(idle.start >= fc.HINT_QUIET,
                      f"the hint pulsed {idle.start:.1f} s after tapping {card}, before the "
                      f"table had been left alone for {fc.HINT_QUIET:.0f} s")
            b = fc.read_board()
            hinted = fc.card_at(b, idle.box) if b else None
            ui.expect(hinted, f"the pulse at {idle.box} px is not over a card")
            caselog.step(f"Tap the hinted card, {hinted}")
            fc.tap_card(b, hinted, settle=1.6)
            ui.answer_prompt("tip")
            played = fc.settled_board()
            c.shot(ui.shoot("AutoHintPlayed"))
            ui.expect(played is not None and played.cards.get(hinted) != b.cards[hinted],
                      f"tapping the hinted {hinted} did not move it")
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            ui.confirm_switch(AUTO_HINT, True, fc.AUTO_HINT, "opened from the table")
            ui.switch_to(AUTO_HINT, False, fc.AUTO_HINT, "AutoHintOptionBackOff")
            hint_maybe_on = False
            ui.back()
            ui.expect(ui.at_table(), "back from Options did not return to the table")
            c.note(f"ON: still for {idle.start:.1f} s after tapping {card}, then {hinted} "
                   f"pulsed as the hint; tapping it played it; switched back OFF")
    finally:
        if hint_maybe_on:
            ui.restore_auto_hint()

    spacing_maybe_off = False
    raised = None
    try:
        with caselog.case("OP-15") as c:
            b, pile = fc.build_long_pile(PILE)
            c.shot(ui.shoot("CardSpacingPile"))
            low = _toggle_lower(b.top_y)
            ui.expect(low > b.top_y + SHIFT, f"tap to lower did not drop the playfield "
                                             f"(top {b.top_y:.0f} -> {low:.0f} pt)")
            raised = b.top_y
            folded_shot = c.shot(ui.settled_shot("CardSpacingArrow"))
            caselog.step(f"Check an arrow sits on top of the {len(pile)}-card pile and its top "
                         "cards are tucked under the next")
            arrow = ui.spacing_arrow(folded_shot)
            lowered = fc.read_board()
            tucked = fc.folded(lowered, pile)
            ui.expect(arrow, f"no arrow over the {len(pile)}-card pile with {fc.SPACING} at its "
                             f"default (see {folded_shot})")
            ui.expect(tucked, f"the arrow shows but no card of the pile is tucked away "
                              f"(gaps {fc.pile_gaps(lowered, pile)} pt)")
            caselog.step("Tap the arrow on top of the pile")
            helpers.wda_tap(arrow, settle=1.5)
            opened_shot = c.shot(ui.settled_shot("CardSpacingExpanded"))
            caselog.step("Check the arrow is gone and every card of the pile shows its rank")
            opened = fc.read_board()
            still = fc.folded(opened, pile)
            ui.expect(not ui.spacing_arrow(opened_shot),
                      f"the arrow is still over the pile after tapping it (see {opened_shot})")
            ui.expect(not still, f"tapping the arrow left {still} tucked away "
                                 f"(gaps {fc.pile_gaps(opened, pile)} pt)")
            c.note(f"{len(pile)}-card pile, playfield lowered: {', '.join(tucked)} tucked under "
                   f"an arrow; tapping it spread all {len(pile)} cards "
                   f"{min(fc.pile_gaps(opened, pile)):.0f} pt apart")

        with caselog.case("OP-16") as c:
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            fc.confirm_spacing(True, "opened from the table — its default")
            ui.expect(fc.set_spacing(False), f"could not turn {fc.SPACING} OFF")
            spacing_maybe_off = True
            fc.confirm_spacing(False, "after setting it")
            c.shot(ui.shoot("CardSpacingOptionOff"))
            off_shot = c.shot(ui.back_to_table_shot("CardSpacingOff"))
            caselog.step(f"Check there is no arrow and all {len(pile)} cards of the pile show")
            off = fc.read_board()
            hidden = fc.folded(off, pile)
            ui.expect(not ui.spacing_arrow(off_shot),
                      f"{fc.SPACING} OFF still draws the arrow over the pile (see {off_shot})")
            ui.expect(not hidden, f"{fc.SPACING} OFF still tucks {hidden} away "
                                  f"(gaps {fc.pile_gaps(off, pile)} pt)")
            ui.expect(ui.open_options(from_table=True), "in-game menu → options did not open")
            fc.confirm_spacing(False, "opened from the table")
            ui.expect(fc.set_spacing(True), f"could not turn {fc.SPACING} back ON")
            spacing_maybe_off = False
            fc.confirm_spacing(True, "after setting it")
            again_shot = c.shot(ui.back_to_table_shot("CardSpacingBackOn"))
            caselog.step("Check the arrow is back on top of the pile")
            ui.expect(ui.spacing_arrow(again_shot),
                      f"{fc.SPACING} back ON did not fold the pile under its arrow "
                      f"(see {again_shot})")
            back = _toggle_lower(_top_y())
            ui.expect(abs(back - raised) <= SHIFT / 3,
                      f"tap to raise did not bring the playfield back (top {back:.0f}, "
                      f"started at {raised:.0f} pt)")
            raised = None
            c.note(f"OFF: no arrow, all {len(pile)} cards shown "
                   f"{min(fc.pile_gaps(off, pile)):.0f} pt apart; back ON the arrow returned")
    finally:
        if spacing_maybe_off:
            fc.restore_spacing()
        if raised is not None:
            _raise_back()

    ui.expect(ui.to_menu(), "could not return to the menu after the table")
    print("PASS: the table plays — controls, timer and score, undo, lower / raise, hints, "
          "drawer, Rich Features, Show Status Bar and Show Card Messages both ways, New, Auto "
          "Hint both ways, and Maintain Card Spacing on a long pile both ways")


if __name__ == "__main__":
    fc.main(run)
