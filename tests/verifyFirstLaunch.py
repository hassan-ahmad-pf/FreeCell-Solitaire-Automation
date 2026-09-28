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

import helpers
import freecell_ui as ui


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


def _reveal_terms_card() -> bool:
    """True when the T&C card is up, allowing ATT-first if needed."""
    if ui.is_on("att_prompt"):
        if not ui.tap("att_allow", settle=2.0):
            raise AssertionError("the tracking prompt blocked the Terms card")
        return ui.seen("tc_continue", timeout=12.0)
    if ui.seen("tc_continue", timeout=8.0):
        return True
    if ui.seen("att_prompt", timeout=8.0):
        if not ui.tap("att_allow", settle=2.0):
            raise AssertionError("the tracking prompt blocked the Terms card")
        return ui.seen("tc_continue", timeout=12.0)
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

    if not ui.tap(link, settle=3.0):
        raise AssertionError(f"could not tap the card's {label} link")
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


def run() -> None:
    _start_without_clearing_overlays()
    card_was_up = _reveal_terms_card()
    failure = None
    try:
        if card_was_up:
            for spec in LINKS:
                _walk_link(*spec)
        else:
            print("  no Terms & Conditions card — link checks skipped")
    except Exception as exc:  # noqa: BLE001
        failure = exc

    shot = _finish_on_menu()
    if os.environ.get("SKIP_OFFLINE") != "1":
        if not ui.ensure_offline():
            raise AssertionError(
                "could not enable Airplane Mode / turn Wi-Fi off after "
                "first launch — later cases would be ad-interrupted"
            )
    if failure:
        raise failure
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
