#!/usr/bin/env python3
"""Build a 13-card pile on the phone for Maintain Card Spacing.

Uses fc.build_long_pile: a deal seen before replays its saved recipe
(no search); a new deal is planned once and stored in
tests/freecell_suite/long_pile_recipes.json so the next run is cheaper.

Phone unlocked, WDA up. Starts from the menu and deals Easy if needed.

  PYTHONPATH=$PWD ./.venv/bin/python -u scripts/build_long_pile.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tests", "freecell_suite")]

import fc  # noqa: E402
import freecell_ui as ui  # noqa: E402


def run() -> None:
    fc.menu()
    if not ui.at_table(timeout=2.0):
        fc.enter_game("easy")
    ui.expect(ui.at_table(timeout=8.0), "could not reach a game table")
    ui.await_rules_prompt()
    board, pile = fc.build_long_pile()
    print(f"PASS: {len(pile)}-card pile ({', '.join(pile[:3])} … {pile[-1]})")


if __name__ == "__main__":
    fc.main(run)
