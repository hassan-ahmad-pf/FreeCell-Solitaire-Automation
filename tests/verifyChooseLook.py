#!/usr/bin/env python3
"""Choose Look applies a different Surface and Cards palette to the table.

Opens the modal, reads the current Surface and Cards selections from the
white frames, taps a random palette that is a different colour on each tab,
deals Easy, and asserts the table felt and the hint-widget card backs both
changed. Matching the tapped swatch is a second check, so a pick that only
repaints the modal still fails.

Puts Surface 1 / Cards 1 back from a finally. The menu icon crops bake the
felt, so leaving a new look on would break later suite cases and this case
the next time it runs.
"""
from __future__ import annotations

import sys

import freecell_ui as ui


CHANGE_TOL = 0.10
MATCH_FELT = 0.10
MATCH_CARDS = 0.18


def run() -> None:
    ui.expect(ui.launch_to_menu(), "could not reach the main menu")

    ui.expect(ui.open_choose_look(), "Choose Look did not open")
    ui.expect(not ui.on_menu(timeout=1.0),
              "on_menu() stayed True while Choose Look was open")
    ui.expect(ui.open_look_tab("surface"), "Surface heading was not tappable")
    shot_s = ui.shoot("ChooseLookSurface")

    surface = ui.look_pick_other("surface")
    ui.expect(surface is not None, "could not pick a Surface other than the current one")
    surface_n, old_surface, new_surface = surface
    print(f"  Surface: left {ui.colour_text(old_surface)}, "
          f"chose palette {surface_n} {ui.colour_text(new_surface)}")

    ui.expect(ui.open_look_tab("cards"), "Cards heading was not tappable")
    shot_c = ui.shoot("ChooseLookCards")
    cards = ui.look_pick_other("cards")
    ui.expect(cards is not None, "could not pick a Cards palette other than the current one")
    cards_n, old_cards, new_cards = cards
    print(f"  Cards: left {ui.colour_text(old_cards)}, "
          f"chose palette {cards_n} {ui.colour_text(new_cards)}")

    restored = False
    try:
        ui.expect(ui.close_choose_look(), "Choose Look close was not tappable")
        ui.expect(ui.on_menu(timeout=6.0),
                  "closing Choose Look did not return to the main menu")

        if not ui.start_game("easy"):
            ui.expect(ui.on_painted_table(),
                      "Easy did not reach the table after the new look")
        ui.start_deal()
        shot_t = ui.shoot("ChooseLookTable")

        felt = ui.felt_colour()
        ui.expect(felt is not None,
                  f"could not find a clear patch of table felt (see {shot_t})")
        felt_change = ui.colour_dist(old_surface, felt)
        ui.expect(felt_change > CHANGE_TOL,
                  f"table surface did not change after Surface {surface_n}: "
                  f"{ui.colour_text(old_surface)} -> {ui.colour_text(felt)} "
                  f"({felt_change:.3f} apart, need > {CHANGE_TOL})")
        felt_match = ui.colour_dist(felt, new_surface)
        ui.expect(felt_match <= MATCH_FELT,
                  f"table felt {ui.colour_text(felt)} is not Surface {surface_n} "
                  f"{ui.colour_text(new_surface)} — {felt_match:.3f} apart "
                  f"(bar {MATCH_FELT}, see {shot_t})")
        print(f"  table felt changed ({felt_change:.3f}) and matches "
              f"Surface {surface_n} ({felt_match:.3f})")

        backs = ui.back_colour()
        ui.expect(backs is not None,
                  f"could not read the hint-widget card backs (see {shot_t})")
        cards_change = ui.colour_dist(old_cards, backs)
        ui.expect(cards_change > CHANGE_TOL,
                  f"card backs did not change after Cards {cards_n}: "
                  f"{ui.colour_text(old_cards)} -> {ui.colour_text(backs)} "
                  f"({cards_change:.3f} apart, need > {CHANGE_TOL})")
        cards_match = ui.colour_dist(backs, new_cards)
        ui.expect(cards_match <= MATCH_CARDS,
                  f"card backs {ui.colour_text(backs)} are not Cards {cards_n} "
                  f"{ui.colour_text(new_cards)} — {cards_match:.3f} apart "
                  f"(bar {MATCH_CARDS}, see {shot_t})")
        print(f"  card backs changed ({cards_change:.3f}) and match "
              f"Cards {cards_n} ({cards_match:.3f})")
    finally:
        restored = ui.restore_default_look()

    ui.expect(restored, "the default look could not be put back — later "
                        "menu icon crops will miss until it is restored by hand")
    ui.expect(ui.to_menu(), "could not return to the menu after Choose Look")
    print(f"PASS: Choose Look — random Surface {surface_n} and Cards {cards_n} "
          f"reached the table and the default look is back — "
          f"{shot_s}, {shot_c}, {shot_t}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        sys.exit(1)
