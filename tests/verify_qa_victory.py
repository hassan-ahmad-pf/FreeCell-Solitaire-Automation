#!/usr/bin/env python3
"""Verify FreeCell's QA gesture, synthetic win, and victory navigation."""
from __future__ import annotations

import sys

import freecell_ui as ui


def main() -> int:
    try:
        if not ui.launch_to_menu():
            raise AssertionError("FreeCell did not reach the main menu")
        if not ui.open_dev_panel():
            raise AssertionError("QA gesture did not reveal the FreeCell QA entry point")
        if not ui.enter_qa_code():
            raise AssertionError("QA code did not open the FreeCell QA panel")
        if not ui.tap("menu_play"):
            raise AssertionError("Play could not be opened")
        if not ui.expect_screen("table"):
            raise AssertionError("Play did not reach the FreeCell table")
        if not ui.complete_game():
            raise AssertionError("Synthetic Complete/Win Game did not reach victory")
        shot = ui.helpers.screenshot("freecell_victory")
        required = ("victory_title", "victory_back")
        missing = [name for name in required if not ui.is_on(name)]
        if missing:
            raise AssertionError(f"victory screen missing: {missing}; see {shot}")
        if not ui.tap("victory_back") or not ui.expect_screen("menu"):
            raise AssertionError("victory back did not return to the menu")
        print(f"PASS: FreeCell QA win and victory navigation — {shot}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
