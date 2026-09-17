#!/usr/bin/env python3
"""Verify FreeCell's QA gesture, synthetic win, and victory navigation."""
from __future__ import annotations

import sys

import freecell_ui as ui


def main() -> int:
    try:
        if not ui.launch_to_menu(force=True):
            raise AssertionError("FreeCell did not reach the main menu")
        if not ui.open_dev_panel():
            raise AssertionError("QA gesture did not reveal the FreeCell QA entry point")
        if not ui.start_game("easy"):
            raise AssertionError("Easy did not reach the FreeCell table")
        if not ui.complete_game():
            raise AssertionError("Synthetic Complete/Win Game did not reach victory")
        shot = ui.helpers.screenshot("freecell_victory")
        required = ("victory_title", "victory_menu")
        missing = [name for name in required if not ui.is_on(name)]
        if missing:
            raise AssertionError(f"victory screen missing: {missing}; see {shot}")
        if not ui.tap("victory_menu"):
            raise AssertionError("victory menu control was not present")
        # On the online build this action can open a cross-promo interstitial.
        # A force launch is only cleanup here; the tap itself was exercised.
        if not ui.launch_to_menu(force=True):
            raise AssertionError("could not recover to the FreeCell menu")
        print(f"PASS: FreeCell QA win and victory navigation — {shot}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
