#!/usr/bin/env python3
"""First-launch Terms/Privacy links, then Continue and ATT, to the menu.

On a fresh install this opens both policy links before Continue consumes the
card. Continue and Allow are then cleared. If the card is already gone
(subsequent device), the link walk is skipped and the test still leaves
FreeCell on the main menu.

If the card is up but a bootstrap crop is missing, the screen is saved, the
miss is named, and the gates are still cleared so later tests are not stranded.

Prereqs: WDA up, iPhone unlocked, DEVICE_UDID set.
Run:  ./.venv/bin/python tests/verifyFirstLaunch.py
"""
from __future__ import annotations

import os
import sys
import time

import caselog
import helpers
import freecell_ui as ui


FRESH_INSTALL_CASES = ("FL-02", "FL-03", "FL-04", "FL-05")

LINKS = (
    ("terms", "tc_terms_link", "tc_terms_page", "Terms & Conditions"),
    ("privacy", "tc_privacy_link", "tc_privacy_page", "Privacy Policy"),
)


def _start_without_clearing_overlays() -> None:
    """Launch without dismissing a first-launch gate already on screen."""
    helpers.connect()
    helpers.launch_app(force=False)
    if ui.seen("tc_continue", timeout=4.0) or ui.seen("att_prompt", timeout=4.0):
        return
    helpers.terminate()
    time.sleep(1.5)
    helpers.launch_app(force=True)


def _reveal_terms_card(timeout: float = 16.0) -> bool:
    """True when the T&C card is up. The tracking prompt can come first or
    land on top of the card a moment later; Allow it either way."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ui.answer_tracking():
            continue
        if ui.is_on("tc_continue"):
            time.sleep(1.0)
            if not ui.answer_tracking():
                return True
            continue
        time.sleep(0.4)
    return False


def _walk_link(tag: str, link: str, page: str, label: str) -> None:
    missing = [name for name in (link, page) if not ui.have(name)]
    if missing:
        shot = helpers.screenshot("first_launch_terms_gate")
        verb = "is" if len(missing) == 1 else "are"
        raise AssertionError(
            f"the fresh-install card is up, but {', '.join(missing)} {verb} "
            f"missing from assets. Crop the link and the {label} page from "
            f"this device before retrying (see {shot})"
        )

    ui.answer_tracking()
    if not ui.tap_policy_link(link):
        if not (ui.answer_tracking() and ui.tap_policy_link(link)):
            missed = helpers.screenshot(f"first_launch_{tag}_link_missed")
            raise AssertionError(
                f"could not tap the card's {label} link (see {missed})")
    shot = None
    try:
        if not ui.seen(page, timeout=12.0):
            failed = helpers.screenshot(f"first_launch_{tag}_page_failed")
            raise AssertionError(
                f"the {label} link did not open the expected page (see {failed})"
            )
        shot = helpers.screenshot(f"first_launch_{tag}_page")
    finally:
        where = f" (see {shot})" if shot else ""
        if not ui.close_web_page():
            raise AssertionError(f"could not close the {label} page{where}")
    if not ui.seen("tc_continue", timeout=8.0):
        raise AssertionError(
            f"closing the {label} page did not return to the Terms card"
        )
    print(f"  {label} link opened its page and returned to the card")


def _finish_on_menu() -> str:
    ui.clear_overlays()
    if not ui.on_menu(6.0):
        time.sleep(2.0)
        ui.clear_overlays()
    if not ui.on_menu(6.0):
        if not ui.launch_to_menu():
            raise AssertionError("FreeCell did not reach the main menu")
    return str(helpers.screenshot("first_launch"))


def _online_for_links() -> None:
    """Only a fresh install needs the network: its policy links load pages.

    The suite runner goes online in Settings before FreeCell first opens, so
    the card is already on a connected phone. Otherwise online() closes
    FreeCell first; relaunch onto the card, which returns because Continue
    has not been pressed yet.
    """
    if ui.known_online():
        print("  Terms card is up — the phone is already online for the policy links",
              flush=True)
        return
    print("  Terms card is up — closing FreeCell and going online for the "
          "policy links", flush=True)
    if not ui.online():
        raise AssertionError("could not go online for the policy links")
    helpers.launch_app(force=False)
    if not _reveal_terms_card():
        raise AssertionError(
            "the Terms card did not come back after going online (see "
            f"{helpers.screenshot('first_launch_online_no_card')})")


def _answer_gates_then_offline() -> None:
    """Continue, Allow ATT if it is already up, then go offline at once.

    Any time FreeCell spends online past the gates can load an interstitial
    that fires later in the offline run. An ATT prompt that arrives late is
    Allowed over Settings while the radios change, or on the offline
    relaunch (offline() kills FreeCell once the radios are off).
    """
    ui.clear_overlays()
    if not ui.offline():
        raise AssertionError(
            "could not go offline right after the first-launch gates — "
            "later cases would be ad-interrupted")
    print("  gates answered — offline again before waiting for the menu",
          flush=True)


def run() -> None:
    suite = (os.environ.get("SKIP_OFFLINE") != "1"
             and os.environ.get("FREECELL_SUITE") == "1")
    _start_without_clearing_overlays()
    card_was_up = _reveal_terms_card()
    went_online = False
    failure = None
    try:
        if card_was_up and suite:
            went_online = True
            _online_for_links()
        if card_was_up:
            for spec in LINKS:
                _walk_link(*spec)
        else:
            print("  no Terms & Conditions card — link checks skipped")
    except Exception as exc:  # noqa: BLE001
        failure = exc

    try:
        if went_online:
            _answer_gates_then_offline()
        shot = _finish_on_menu()
    except Exception as exc:  # noqa: BLE001
        if failure:
            raise AssertionError(f"{failure}; then {exc}") from exc
        raise
    if suite:
        if not ui.ensure_offline():
            raise AssertionError(
                "could not enable Airplane Mode / turn Wi-Fi off after "
                "first launch — later cases would be ad-interrupted"
            )
    if failure:
        raise failure
    if not card_was_up:
        for cid in FRESH_INSTALL_CASES:
            caselog.skip(cid, "no Terms & Conditions card — FreeCell was "
                              "already opened on this install")
    print(
        "PASS: first launch checked the policy links when available, then "
        f"reached the main menu (see {shot})"
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
