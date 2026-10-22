#!/usr/bin/env python3
"""verifyFirstLaunch: first-launch gates, then the offline menu.

FL-04  the Terms card's Terms & Conditions link opens the terms page
FL-05  its Privacy Policy link opens the privacy page
FL-02  Continue clears the Terms card
FL-03  the tracking prompt shows; Allow clears it (it may come before the card)
FL-01  force-quit and reopen reaches the main menu

FL-02..05 need FreeCell deleted, reinstalled and NOT opened before the run;
without the card they are skipped. The policy pages load online; while
still online, Options' Game Center switch is made sure of (FreeCell turns it
off when its first sign-in does not finish); then the phone goes offline for
the offline tests.

Run:  ./.venv/bin/python -u tests/freecell_suite/verifyFirstLaunch.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [HERE, ROOT]

import caselog  # noqa: E402
import config  # noqa: E402
import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402
import helpers  # noqa: E402

FRESH_INSTALL = ("FL-04", "FL-05", "FL-02", "FL-03")
ATT_WAIT = 12.0
_ATT_SEEN = []


def _freecell_first_launch():
    """tests/verifyFirstLaunch.py — its link walk is proven on this device."""
    path = os.path.join(ROOT, "tests", "verifyFirstLaunch.py")
    spec = importlib.util.spec_from_file_location("freecell_first_launch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _allow_tracking() -> bool:
    if ui.answer_tracking():
        _ATT_SEEN.append(time.time())
        return True
    return False


def _reveal_card(timeout: float = 16.0) -> bool:
    """True when the Terms card is up; a tracking prompt on the way is Allowed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _allow_tracking():
            continue
        if ui.is_on("tc_continue"):
            time.sleep(1.0)
            if not _allow_tracking():
                return True
            continue
        time.sleep(0.4)
    return False


def _game_center_while_online() -> None:
    """Not a case of its own: a miss here is left to verifyVictory, which
    makes sure of the switch again before its win."""
    try:
        if helpers.in_app() and fc.ad_up():
            fc.close_ad("first launch")
        ui.expect(ui.on_menu(15.0), "the main menu is not showing")
        fc.game_center_on()
    except Exception as exc:  # noqa: BLE001
        print(f"  Game Center switch not checked here ({exc}); verifyVictory checks it",
              flush=True)


def run() -> None:
    first = _freecell_first_launch()
    first._reveal_terms_card = _reveal_card
    first._start_without_clearing_overlays()
    card = _reveal_card()

    if card:
        first._online_for_links()
        with caselog.case("FL-04") as c:
            first._walk_link(*first.LINKS[0])
            c.shot(config.LOG / "first_launch_terms_page.png")
            c.note("Terms & Conditions page opened and closed back to the card")
        with caselog.case("FL-05") as c:
            first._walk_link(*first.LINKS[1])
            c.shot(config.LOG / "first_launch_privacy_page.png")
            c.note("Privacy Policy page opened and closed back to the card")
        with caselog.case("FL-02") as c:
            c.shot(ui.shoot("FirstLaunchTerms"))
            ui.expect(ui.tap("tc_continue", settle=2.0), "Continue could not be tapped")
            deadline = time.time() + 6.0
            while ui.is_on("tc_continue") and time.time() < deadline:
                _allow_tracking()
                time.sleep(0.5)
            caselog.step("Check the Terms card is gone")
            ui.expect(not ui.is_on("tc_continue"), "the Terms card stayed up after Continue")
            c.note("Continue cleared the Terms card")
        with caselog.case("FL-03") as c:
            caselog.step("Check the App Tracking prompt showed and was Allowed")
            deadline = time.time() + ATT_WAIT
            while not _ATT_SEEN and time.time() < deadline:
                _allow_tracking() or time.sleep(0.5)
            ui.expect(_ATT_SEEN, f"the tracking prompt never showed within {ATT_WAIT:.0f}s "
                                 "(is Settings → Privacy → Tracking → Allow Apps to "
                                 "Request to Track on?)")
            ui.expect(not helpers.alert_text(), "a prompt is still up after Allow")
            c.note("tracking prompt shown and Allowed")
    else:
        for cid in FRESH_INSTALL:
            caselog.skip(cid, "no Terms & Conditions card — FreeCell was already "
                              "opened on this install")

    if ui.known_online():
        _game_center_while_online()

    ui.expect(ui.offline(restore=False), "could not enable Airplane Mode / turn Wi-Fi off "
                                         "— the offline tests would be ad-interrupted")
    print("  offline for the offline tests", flush=True)

    with caselog.case("FL-01") as c:
        caselog.step("Force-quit FreeCell and open it again")
        helpers.launch_app(force=True)
        ui.app_launched()
        ui.clear_overlays()
        ui.settle_prompts()
        caselog.step("Check FreeCell reopened on the main menu with no Terms card")
        ui.expect(ui.on_menu(15.0), "force-quit and reopen did not reach the main menu")
        ui.expect(not ui.is_on("tc_continue"), "the Terms card came back after reopening")
        c.shot(ui.shoot("FirstLaunch"))
        c.note("reopened onto the main menu, no pop-up left")

    print("PASS: first launch — " + ("policy links, Continue and tracking checked, "
                                     if card else "no Terms card on this install, ")
          + "then force-quit and reopen reached the offline main menu")


if __name__ == "__main__":
    fc.main(run)
