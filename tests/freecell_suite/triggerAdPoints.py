#!/usr/bin/env python3
"""triggerAdPoints: where a full-screen ad must fire, and where it must not. [ONLINE]

Rules from the cardgames develop branch (FreeCell):

* The 30 s wait is how long FreeCell has been open on screen, including the
  menu. Background time does not count. It starts when the ad appears
  (showAd), not when it closes.
* Leaving the table asks for an ad: Help, Options, FAQ, Back, Abandon (Yes),
  New, Replay, Play → Easy. The ask is immediate; the ad itself can take a
  few seconds to fill.
* A win asks for an ad about 5 s later.
* Resume never asks. Abandon → No stays on the table, so it does not ask.
* Victory → New inside the 30 s wait must not show an ad (same gate as
  every other leave). After 30 s it must.
* After an interstitial actually shows, canShow stays false until New or
  Replay (faAnyAxLastInterstitialishDisplay). 30 s alone does not clear it.
  The run therefore News inside the cooldown before the next leave/win.
* QA is unlocked only so Synthetic Win works. A QA ad-network pin would
  turn the 30 s wait off, so this module never sets one.

After going online, any interstitial already in cache is played and closed
(there is no flush). The 30 s cooldown starts from that wasted ad. Each
expect-ad case retries once from a clean screen if the first ask did not
fill. After every case the run puts itself back on the table or the menu
so the next case does not inherit a Help page, Victory, or an unclosed ad.

Run:  ./.venv/bin/python -u tests/freecell_suite/triggerAdPoints.py
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
from caselog import says  # noqa: E402

# 30 s compiled wait from the moment the ad *appears* (not when it closes).
COOLDOWN = 32.0
# Live 7.42.1 still lands leave-game ads ~13–20 s after the tap. 10 s was
# too short: Help/Abandon/Win failed, then the same ad showed up on Resume.
LEAVE_WAIT = 25.0
# Win ask is ~5 s later, then the same late fill.
WIN_WAIT = 28.0
# Long enough to catch a late fill, short enough that a true no-ad is quick.
NO_AD = 8.0

DESTINATIONS = {
    "options": ("drawer_options", lambda: ui.expect_screen("options", timeout=0.5)),
    "help": ("drawer_help", lambda: ui.expect_screen("help", timeout=0.5)),
    "faq": ("drawer_faq", lambda: ui.is_on("screen_faq")),
}

_last_ad = 0.0
# True after an interstitial appears until a quiet New (clone:
# faAnyAxLastInterstitialishDisplay). canShow is false while this is set.
_flag_dirty = False


def _now() -> float:
    return time.monotonic()


def _stamp() -> None:
    global _last_ad, _flag_dirty
    _last_ad = _now()
    _flag_dirty = True


def _since_ad() -> float:
    return 1e9 if not _last_ad else _now() - _last_ad


def _manual_note(c, where: str) -> None:
    if where in fc.MANUAL_CLOSES:
        c.note("passed manually — the ad was closed by hand")


def _close(where: str) -> None:
    """Close an ad that was already stamped when it appeared."""
    fc.close_or_wait(where)


def _arm(where: str) -> None:
    """Sit until the 30 s open-time wait has passed. No card play — a mid-wait
    Victory used to eat the clock and skip the real trigger."""
    left = COOLDOWN - _since_ad()
    if left > 0.4:
        caselog.wait(left, f"the 30s cooldown before {where}")


def _watch_no_ad(where: str, arrived) -> None:
    """The expected screen arrives, and no interstitial follows in NO_AD."""
    caselog.step(f"Check {where} opened with no interstitial")
    deadline = time.time() + NO_AD
    while not arrived():
        ui.expect(helpers.in_app(), f"FreeCell left the screen during {where}: "
                                    f"{helpers.active_app()}")
        ui.expect(not fc.ad_up(), f"an interstitial appeared during {where}")
        ui.expect(time.time() < deadline, f"{where} did not arrive within {NO_AD:.0f}s")
        time.sleep(0.2)
    while time.time() < deadline:
        ui.expect(helpers.in_app(), f"FreeCell left the screen during {where}: "
                                    f"{helpers.active_app()}")
        ui.expect(not fc.ad_up(), f"an interstitial appeared after {where} opened")
        time.sleep(0.2)
    print(f"  {where}: no interstitial", flush=True)


def _wait_ad(where: str, wait: float) -> bool:
    """Watch until an interstitial is up. The 30 s clock starts on appear."""
    start = time.time()
    if not fc.wait_ad(timeout=wait):
        return False
    _stamp()
    caselog.step("Check an interstitial is up inside FreeCell")
    print(f"  {where}: interstitial up after {time.time() - start:.0f}s — "
          "30s cooldown starts now; closing", flush=True)
    _close(where)
    return True


def _claim_late(where: str) -> bool:
    """An ad that lands after the wait, often while we are recovering
    (Resume / Back). That is still the leave/win ad, not a new trigger."""
    if not fc.ad_up():
        return False
    caselog.step(f"A late interstitial came up after {where} — that is the fill, not Resume")
    print(f"  {where}: the ad landed late, after the first watch — "
          "taking it as this trigger and closing it", flush=True)
    _stamp()
    print(f"  {where}: 30s cooldown starts now (ad appeared)", flush=True)
    _close(f"{where} (late)")
    return True


def _need_table() -> None:
    if ui.at_table(timeout=2.0):
        return
    _recover("table")
    ui.expect(ui.at_table(timeout=4.0), "could not reach the gameplay screen")


def _need_menu() -> None:
    if ui.on_menu(2.0):
        return
    _recover("menu")
    ui.expect(ui.on_menu(4.0), "could not reach the main menu")


def _recover(want: str) -> bool:
    """Best-effort return to the table or the menu. True when an interstitial
    was up and closed (a late fill from the last trigger, not a new one)."""
    ate = False

    def eat(where: str) -> None:
        nonlocal ate
        if not fc.ad_up():
            return
        print(f"  recover: an interstitial is up ({where}) — late fill from the last trigger",
              flush=True)
        _stamp()
        _close(where)
        ate = True

    try:
        eat(f"leftover before {want}")
        if want == "table" and ui.at_table(timeout=1.5):
            return ate
        if want == "menu" and ui.on_menu(1.5):
            return ate
        if want == "victory" and ui.expect_screen("victory", timeout=0.8):
            return ate
        ui.settle_prompts()
        eat(f"leftover after prompts ({want})")
        if want == "table" and ui.at_table(timeout=1.5):
            return ate
        if want == "menu" and ui.on_menu(1.5):
            return ate
        if ui.expect_screen("options", timeout=0.4) or ui.expect_screen("help", timeout=0.4) \
                or ui.is_on("screen_faq"):
            ui.back()
            eat("leftover after backing out of a page")
            if want == "table" and ui.at_table(timeout=6.0):
                return ate
            if want == "menu" and ui.on_menu(3.0):
                return ate
        if ui.expect_screen("victory", timeout=0.5):
            if want == "victory":
                return ate
            ui.leave_victory()
            eat("leftover leaving Victory")
            if want == "menu" and ui.on_menu(4.0):
                return ate
            fc.enter_from_menu(deal=True)
            eat("leftover after Victory → Easy")
            ui.settle_prompts()
            if ui.at_table(timeout=8.0):
                if want == "menu":
                    _tap_back()
                    eat("Back while recovering to the menu")
                return ate
        if ui.at_table(timeout=1.0):
            if want == "table":
                return ate
            _tap_back()
            eat("Back while recovering to the menu")
            if ui.on_menu(8.0):
                return ate
        if not ui.on_menu(2.0):
            fc.menu()
            eat("leftover on the way to the menu")
        if want == "menu":
            return ate
        fc.enter_from_menu(deal=False)
        eat(f"{want} resume")
        ui.settle_prompts()
        if ui.at_table(timeout=6.0):
            return ate
        fc.enter_game("easy")
        eat(f"{want} deal")
        ui.settle_prompts()
    except Exception as exc:  # noqa: BLE001
        print(f"  recover to {want} failed ({exc})", flush=True)
    return ate


@says(lambda dest: f"Open the table drawer and tap {dest.title()}")
def _open(dest: str) -> None:
    _need_table()
    anchor, _ = DESTINATIONS[dest]
    ui.expect(ui.open_table_drawer(), f"the table drawer did not open before {dest}")
    ui.expect(ui.tap(anchor, settle=1.0), f"could not tap the drawer's {dest}")


@says("Tap Back on the gameplay screen")
def _tap_back() -> None:
    ui.expect(ui.tap("back_game", settle=1.0), "the table's Back could not be tapped")


@says("Tap New on Victory")
def _victory_new() -> None:
    ui.expect(ui.expect_screen("victory", timeout=4.0), "Victory is not showing for New")
    ui.expect(ui.tap("victory_new", settle=1.0), "Victory's New could not be tapped")


@says("Tap New on the table menu (clears the one-shot interstitial flag)")
def _table_new() -> None:
    """Clone newGameWithButtonIndex: faResetAxLastInterstitialishDisplay,
    then swapPage. Zero moves skips the abandon alert."""
    _need_table()
    ui.expect(ui.open_table_drawer(), "the table drawer did not open before New")
    ui.expect(ui.tap("drawer_new", settle=1.0), "could not tap the drawer's New")
    if fc.wait_alert("abandon", timeout=2.0):
        helpers.answer_alert("Yes", settle=1.0)


def _clear_flag(why: str) -> None:
    """After a shown interstitial, the next leave/win is skipped until New.

    Must not raise (it sits between cases). Must not go menu → Easy/Resume
    — that is another ask. Must not wait for a fill after New; a 2 s poll
    was catching leftovers and counting them as a new show."""
    global _flag_dirty
    if not _flag_dirty:
        print(f"  clone: one-shot flag already clear before {why}", flush=True)
        return
    print(f"  clone: New to clear the one-shot flag before {why}", flush=True)
    try:
        if fc.ad_up():
            _stamp()
            _close(f"leftover before New ({why})")
        if not ui.at_table(timeout=2.0):
            if ui.expect_screen("options", timeout=0.4) or ui.expect_screen("help", timeout=0.4) \
                    or ui.is_on("screen_faq"):
                ui.back()
        if not ui.at_table(timeout=3.0):
            print(f"  clone: no table for New before {why} — not going to "
                  "the menu (that would ask again)", flush=True)
            return
        for step in range(2):
            _table_new()
            time.sleep(0.5)
            if not fc.ad_up():
                _flag_dirty = False
                break
            _stamp()
            _close(f"New while clearing the flag ({why}, {step + 1})")
            print("  clone: New showed an ad — tapping New again immediately "
                  "(still in the 30s window)", flush=True)
        if ui.at_table(timeout=3.0) and not fc.ad_up():
            _flag_dirty = False
    except Exception as exc:  # noqa: BLE001
        print(f"  clone: could not clear the flag before {why} ({exc})",
              flush=True)


@says("Abandon the game from the table menu")
def _abandon() -> None:
    _need_table()
    ui.expect(ui.open_table_drawer(), "the table drawer did not open before Abandon")
    ui.expect(ui.tap("drawer_abandon", settle=1.0), "could not tap the drawer's Abandon")
    if fc.wait_alert("abandon", timeout=3.0):
        helpers.answer_alert("Yes", settle=1.0)


def _leave_ad(where: str, trigger, landed=None) -> None:
    """Arm the 30 s wait, fire a leave-the-table trigger, require an ad.
    One retry from a clean table if the first ask did not fill."""
    for attempt in range(2):
        _need_table()
        _arm(where)
        trigger()
        if _wait_ad(where, LEAVE_WAIT) or _claim_late(where):
            if landed is not None:
                caselog.step(f"Check the interstitial closed onto {landed}")
            return
        shot = ui.shoot("TANoAd")
        ui.expect(not attempt, f"no interstitial after {where} within {LEAVE_WAIT:.0f}s, "
                               f"twice (see {shot})")
        caselog.step(f"No interstitial after {where} — wait 30s again and retry")
        print(f"  no ad after {where} — once more from a clean table", flush=True)
        # Resume / Easy during recover is a different trigger. Counting it as
        # this leave made TA-12 pass the ad check and fail on the menu.
        if _recover("table"):
            print(f"  {where}: an ad during recover was a later trigger, "
                  "not this leave — retrying the leave", flush=True)
        elif _claim_late(where):
            if landed is not None:
                caselog.step(f"Check the interstitial closed onto {landed}")
            return


def _win() -> None:
    _need_table()
    if ui.synthetic_win():
        return
    if fc.ad_up():
        _close("blocker over Synthetic Win")
        _need_table()
        if ui.synthetic_win():
            return
    ui.expect(False, f"Synthetic Win could not be fired (see {ui.shoot('TASyntheticWin')})")


def _fresh_table() -> None:
    """One Easy deal so the session has entered a game (first-game grace),
    then a clean table. Drawer New is not used — that itself asks for an ad."""
    _need_menu()
    fc.enter_game("easy")
    if fc.ad_up():
        _close("fresh-table entry")
        print("  entering the game showed an ad — closed it", flush=True)
    ui.settle_prompts()
    ui.expect(ui.at_table(timeout=8.0), "could not reach a fresh game table")


def run() -> None:
    fc.go_online()
    fc.menu()
    fc.ensure_qa()
    print("  setup: wasting any interstitial that loaded before the trigger cases",
          flush=True)
    if fc.waste_cached_ad():
        _stamp()
        print("  setup: the 30s cooldown now starts from that wasted ad", flush=True)
    else:
        print("  setup: cache was empty — starting the cases on a fresh table",
              flush=True)
    _fresh_table()
    # Do not New here. Waste already showed an ad, so the flag is on and
    # TA-01 (no ad on Options) is true either way. New before TA-01 was
    # showing its own ads and blowing the 30s window.

    with caselog.case("TA-01") as c:
        for attempt in range(2):
            _open("options")
            try:
                _watch_no_ad("Options", DESTINATIONS["options"][1])
                break
            except AssertionError:
                if attempt or not fc.ad_up():
                    raise
                caselog.step("An inherited interstitial came up — close it and retry Options")
                print("  an inherited ad came up — closing it and retrying Options once",
                      flush=True)
                _close("Options retry")
                _recover("table")
        c.shot(ui.shoot("AdShortOptions"))
        c.note("no interstitial — Options opened before 30s on the gameplay screen")
    _recover("table")
    # Still inside the waste-ad cooldown: New now resets the flag and must
    # not show. Then TA-02 can wait 30s and Help can actually fire.
    _clear_flag("Help")

    with caselog.case("TA-02") as c:
        _leave_ad("Help", lambda: _open("help"))
        c.shot(ui.shoot("AdAfterHelp"))
        _manual_note(c, "Help")
        c.note("interstitial after Help, then closed")
    _recover("table")

    with caselog.case("TA-03") as c:
        _open("options")
        _watch_no_ad("Options (still inside the 30s cooldown)", DESTINATIONS["options"][1])
        c.shot(ui.shoot("AdCooldownOptions"))
        c.note("no interstitial — Options still inside the 30s cooldown")
    _recover("table")
    _clear_flag("Abandon")

    with caselog.case("TA-12") as c:
        _leave_ad("Abandon", _abandon, landed="the main menu")
        ui.expect(ui.on_menu(8.0), "Abandon did not land on the main menu after its ad")
        c.shot(ui.shoot("AdAfterAbandon"))
        _manual_note(c, "Abandon")
        c.note("interstitial after Abandon, closed onto the menu")
    _recover("table")
    _clear_flag("Victory")

    with caselog.case("TA-04") as c:
        for attempt in range(2):
            _need_table()
            _arm("Victory")
            _win()
            if _wait_ad("Victory", WIN_WAIT) or _claim_late("Victory"):
                break
            shot = ui.shoot("TANoAd")
            ui.expect(not attempt, f"no interstitial after Victory within {WIN_WAIT:.0f}s, "
                                   f"twice (see {shot})")
            caselog.step("No interstitial after the win — wait 30s and win again")
            print("  no ad after Victory — once more from a loaded table", flush=True)
            if _recover("table") or _claim_late("Victory"):
                print("  Victory: the ad showed up while recovering — counted", flush=True)
                break
        caselog.step("Check the Victory screen is showing after the interstitial closed")
        ui.expect(ui.expect_screen("victory", timeout=8.0),
                  "the Victory screen is not showing after the win ad closed")
        c.shot(ui.shoot("AdVictory"))
        _manual_note(c, "Victory")
        c.note("interstitial over Victory after Synthetic Win, then Victory showing")
    _recover("victory")

    with caselog.case("TA-05") as c:
        if not ui.expect_screen("victory", timeout=3.0):
            print("  Victory is not showing — win once so New can be tapped in cooldown",
                  flush=True)
            _need_table()
            _win()
            if _wait_ad("Victory before New", WIN_WAIT) or _claim_late("Victory before New"):
                print("  a win ad came up — New will be tapped inside that 30s wait",
                      flush=True)
            ui.expect(ui.expect_screen("victory", timeout=8.0),
                      "Victory is not showing for New")
        _victory_new()
        _watch_no_ad("Victory → New (still inside the 30s cooldown)",
                     lambda: ui.at_table(timeout=0.5))
        c.shot(ui.shoot("AdVictoryNewCooldown"))
        c.note("no interstitial — Victory → New still inside the 30s cooldown")
    _recover("table")

    with caselog.case("TA-06") as c:
        # Still inside the win-ad wait if TA-05 was quick: a win now should
        # not ad. Then sit the rest of 30 s on Victory and tap New.
        _need_table()
        _win()
        if _wait_ad("Victory before New", WIN_WAIT) or _claim_late("Victory before New"):
            print("  a win ad came up before New — sitting the rest of 30s on Victory",
                  flush=True)
        ui.expect(ui.expect_screen("victory", timeout=8.0),
                  "Victory is not showing for the 30s New wait")
        _arm("Victory → New")
        _victory_new()
        if not (_wait_ad("Victory → New after 30s", LEAVE_WAIT)
                or _claim_late("Victory → New after 30s")):
            shot = ui.shoot("TANoAd")
            ui.expect(False, f"no interstitial for Victory → New after 30s "
                             f"(see {shot})")
        caselog.step("Check the new deal is on the table after the interstitial")
        if not ui.at_table(timeout=8.0):
            _recover("table")
        ui.expect(ui.at_table(timeout=4.0),
                  "New after 30s on Victory did not reach a table")
        c.shot(ui.shoot("AdVictoryNew"))
        _manual_note(c, "Victory → New after 30s")
        c.note("interstitial on New after 30s on Victory, closed onto the new deal")
    _recover("table")
    _clear_flag("FAQ")

    with caselog.case("TA-10") as c:
        _leave_ad("FAQ", lambda: _open("faq"))
        c.shot(ui.shoot("AdAfterFaq"))
        _manual_note(c, "FAQ")
        c.note("interstitial after FAQ, then closed")
    _recover("table")
    _clear_flag("Back")

    with caselog.case("TA-07") as c:
        _leave_ad("Back", _tap_back, landed="the main menu")
        ui.expect(ui.on_menu(8.0), "the Back ad did not close onto the main menu")
        c.shot(ui.shoot("AdBackMenu"))
        _manual_note(c, "Back")
        c.note("interstitial after Back, closed onto the menu")
    _recover("menu")

    with caselog.case("TA-08") as c:
        _need_menu()
        fc.enter_from_menu(deal=False)
        _watch_no_ad("Play → Resume (still inside the Back-ad cooldown)",
                     lambda: ui.at_table(timeout=0.5))
        c.shot(ui.shoot("AdShortMenuEntry"))
        c.note("no interstitial — Play → Resume still inside the 30s cooldown")
    _recover("table")
    _clear_flag("Play → Easy")
    _tap_back()
    _claim_late("Back before Play → Easy")
    _need_menu()

    with caselog.case("TA-09") as c:
        _need_menu()
        _arm("Play → Easy")
        for attempt in range(2):
            fc.enter_from_menu(deal=True)
            if _wait_ad("Play → Easy", LEAVE_WAIT) or _claim_late("Play → Easy"):
                break
            shot = ui.shoot("TANoAd")
            ui.expect(not attempt, f"no interstitial after Play → Easy within "
                                   f"{LEAVE_WAIT:.0f}s, twice (see {shot})")
            caselog.step("No interstitial on Play → Easy — sit the menu 30s and retry")
            print("  no ad on Play → Easy — once more from the menu", flush=True)
            if _recover("menu") or _claim_late("Play → Easy"):
                print("  Play → Easy: the ad showed up while recovering — counted",
                      flush=True)
                break
            _arm("Play → Easy")
        ui.settle_prompts()
        caselog.step("Check the new deal is on the table after the interstitial")
        if not ui.at_table(timeout=8.0):
            _recover("table")
        ui.expect(ui.at_table(timeout=4.0),
                  "the deal did not reach the table after its ad")
        c.shot(ui.shoot("AdLongMenuEntry"))
        _manual_note(c, "Play → Easy")
        c.note("interstitial on Play → Easy after 30s on the menu, then the new deal")
    _recover("table")
    _clear_flag("Play → Resume after 30s")
    _tap_back()
    _claim_late("Back before Resume after 30s")
    _need_menu()

    with caselog.case("TA-11") as c:
        # Resume never asks, even after 30 s on the menu (cmdResumePlay).
        _need_menu()
        _arm("Play → Resume")
        fc.enter_from_menu(deal=False)
        _watch_no_ad("Play → Resume (after 30s on the menu)",
                     lambda: ui.at_table(timeout=0.5))
        c.shot(ui.shoot("AdLongMenuResume"))
        c.note("no interstitial — Play → Resume after 30s on the menu (Resume never triggers)")
    _recover("menu")

    ui.expect(ui.on_menu(4.0) or ui.to_menu(),
              "could not return to the main menu after the ad checks")
    caselog.raise_if_failed()
    print("PASS: every interstitial trigger and cooldown point behaved as expected")


if __name__ == "__main__":
    fc.main(run)
