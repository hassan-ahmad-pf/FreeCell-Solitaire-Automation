#!/usr/bin/env python3
"""QA gesture, Synthetic Win 90-99%, and the victory ranking screen."""
from __future__ import annotations

import sys

import helpers
import freecell_ui as ui


def run() -> None:
    ui.expect(ui.launch_to_menu(), "FreeCell did not reach the main menu")
    ui.expect(ui.open_dev_panel(),
              "QA gesture did not reveal the FreeCell QA watermark")
    ui.expect(ui.start_game("easy"), "Easy did not reach the FreeCell table")
    ui.expect(ui.complete_game(),
              "90%-99% then WIN did not reach the victory screen")
    shot = helpers.screenshot("freecell_victory")
    missing = [name for name in ("victory_title", "victory_menu") if not ui.is_on(name)]
    ui.expect(not missing, f"victory screen missing: {missing}; see {shot}")
    ui.expect(ui.to_menu(), "could not recover to the FreeCell menu after victory")
    print(f"PASS: QA win reached victory and returned to the menu — {shot}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
