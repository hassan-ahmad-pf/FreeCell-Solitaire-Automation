#!/usr/bin/env python3
"""verifyRelaunch: a moved game survives Home + kill.

RL-01  resume or deal, one move, Home, kill, ~3.5 s, reopen: the same board
RL-02  carry on with that board, one more move, Home, kill, ~35 s, reopen:
       the same board again

Each leg plays its own move and is recorded on its own, so a failed first
leg does not stop the second (the test still ends FAIL).

The kill: terminate through the open session, then wait until
FreeCell is no longer the foreground app; the relaunch starts from the Home
Screen. The board is the exact card layout read from the accessibility tree.
A fresh install reopens straight on the table. After many force-quits
FreeCell instead parks a game in progress on its main menu whenever it goes
to the background (no kill needed); the reopened game is then reached
through Play → Resume. A missing Resume or a changed board fails.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyRelaunch.py
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import caselog  # noqa: E402
import config  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402

LEGS = (("Short", 3.5), ("Long", 35.0))


def _kill() -> float:
    """Terminate the backgrounded app; when it left the foreground.

    Never mints a session — that would bring FreeCell back and undo the
    Home press.
    """
    ui.expect(helpers.cached_session(), "no WDA session to terminate through")
    helpers.terminate()
    for _ in range(24):
        if helpers.active_app() != config.BUNDLE_ID:
            return time.monotonic()
        time.sleep(0.25)
    raise AssertionError("FreeCell was still in the foreground 6s after being terminated — "
                         "it was never killed, so nothing after this would mean anything")


def _back_to_game(tag: str, timeout: float = 20.0):
    """Reach the saved game; how it came back and the reopened screen's shot.

    Never answers the abandon prompt with Yes — that would drop the game
    being checked.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        ui.settle_prompts({"abandon": "No"})
        if ui.at_table(timeout=1.0):
            return "the table came straight back", ui.shoot(f"Relaunch{tag}Reopened")
        ui.close_house_promo()
        if ui.on_menu(timeout=1.0):
            reopened = ui.shoot(f"Relaunch{tag}Reopened")
            ui.expect(ui.tap("menu_play", settle=2.0), "Play control not found on the reopened menu")
            ui.expect(ui.wait_for("difficulty_easy", timeout=6.0), "Play did not open the picker")
            ui.expect(ui.is_on("resume"), f"the picker offers no Resume — the game in progress "
                                          f"was dropped (see {ui.shoot(f'Relaunch{tag}NoResume')})")
            ui.expect(ui.tap("resume", settle=2.0), "Resume could not be tapped")
            ui.expect(ui.at_table(), "Resume did not reach the game table")
            return "reopened on the menu, Play → Resume", reopened
    shot = ui.shoot(f"Relaunch{tag}Lost")
    raise AssertionError(f"FreeCell came back on neither the table nor the menu (alert: "
                         f"{helpers.alert_text()!r}, see {shot})")


def _resume_or_deal() -> str:
    """Carry on with the table, else resume the paused game, else deal Easy."""
    if ui.at_table(timeout=1.0):
        return "carried on with the game on the table"
    fc.menu()
    ui.expect(ui.tap("menu_play", settle=2.0), "Play control not found on the menu")
    ui.expect(ui.wait_for("difficulty_easy", timeout=6.0), "Play did not open the picker")
    if ui.is_on("resume"):
        ui.expect(ui.tap("resume", settle=2.0), "Resume could not be tapped")
        how = "resumed the paused game"
    else:
        ui.expect(ui.tap("difficulty_easy", settle=2.0), "Easy could not be tapped")
        how = "dealt an Easy game"
    ui.expect(ui.at_table(), "did not reach the game table")
    ui.await_rules_prompt()
    return how


def _kill_and_reopen(wait: float, tag: str):
    before = fc.settled_board()
    ui.expect(before is not None and len(before) == 52, "could not read the board")
    ui.expect(helpers.home(), "Home did not leave the table — the save happens on background")
    killed = _kill()
    print(f"  killed — waiting {wait:.1f}s", flush=True)
    time.sleep(wait)
    gap = time.monotonic() - killed
    ui.expect(ui.relaunch_after_kill(), "could not launch FreeCell again")
    ui.expect(helpers.in_app(), f"FreeCell is not the foreground app after the relaunch — "
                                f"{helpers.active_app() or 'WDA would not say which app'} is")
    how, reopened = _back_to_game(tag)
    print(f"  {how}", flush=True)
    after = fc.settled_board()
    shot = ui.shoot(f"Relaunch{tag}")
    ui.expect(after is not None and after == before,
              f"the board changed across the relaunch: {before.moved(after) if after else 'unreadable'} "
              f"(see {shot})")
    return gap, how, reopened, shot


def run() -> None:
    fc.menu()
    for cid, (tag, wait) in zip(("RL-01", "RL-02"), LEGS):
        with caselog.case(cid, soft=True) as c:
            start = _resume_or_deal()
            _, _, card = fc.play_one_move()
            print(f"  {tag}: {start}, moved {card}", flush=True)
            gap, how, reopened, shot = _kill_and_reopen(wait, tag)
            c.shot(reopened)
            c.shot(shot)
            c.note(f"{start}, moved {card}; same board after {gap:.1f}s closed — {how}")
    caselog.raise_if_failed()

    ui.expect(ui.to_menu(), "could not return to the menu after the relaunches")
    print(f"PASS: a move was played and the game came back unchanged after "
          f"{LEGS[0][1]:.1f}s and again after {LEGS[1][1]:.0f}s closed")


if __name__ == "__main__":
    fc.main(run)
