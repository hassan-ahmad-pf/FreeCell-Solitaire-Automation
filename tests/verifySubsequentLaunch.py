#!/usr/bin/env python3
"""Subsequent launch: attach without restarting and land on the menu.

This is the everyday path uploaded cases will use. It must not terminate
FreeCell. First-launch gates must not be present. One Back from a paused
table or picker is allowed.

Prereqs: WDA up, iPhone unlocked, DEVICE_UDID set, T&C already accepted.
Run:  ./.venv/bin/python tests/verifySubsequentLaunch.py
"""
from __future__ import annotations

import sys

import helpers
import freecell_ui as ui


def run() -> None:
    helpers.connect()
    helpers.launch_app(force=False)

    if ui.is_on("tc_continue") or ui.is_on("att_prompt"):
        shot = helpers.screenshot("subsequent_launch_gate")
        raise AssertionError(
            "subsequent launch showed a first-launch gate; this path must "
            f"attach to an already-accepted install (see {shot})"
        )

    if ui.on_menu(3.0):
        shot = helpers.screenshot("subsequent_launch")
        print(f"PASS: attached to FreeCell on the main menu (see {shot})")
        return

    if ui.is_on("back_game") and ui.tap("back_game"):
        if ui.on_menu(4.0):
            shot = helpers.screenshot("subsequent_launch")
            print(
                "PASS: attached and one Back reached the main menu "
                f"(see {shot})"
            )
            return

    shot = helpers.screenshot("subsequent_launch_failed")
    raise AssertionError(
        "attached without restart, but did not reach the main menu "
        f"(see {shot})"
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
