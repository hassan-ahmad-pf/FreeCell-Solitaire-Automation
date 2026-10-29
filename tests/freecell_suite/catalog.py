"""The FreeCell suite: its tests, their cases, and where each one stands.

The suite's case IDs, titles and sections are in docs/testrail/suite_cases.py.
RUN_ORDER is a full run (--all): the six STANDALONE tests in it run only
with --all or when named. Each test's case ids are in the order it runs
them: the console lists them that way before the test starts.

The order visits each screen once, as far as these allow: the first launch
comes first (a fresh install's Terms card), the middle runs offline (no
interstitial over a deal), QA is unlocked before the tests that win with it,
More Games runs before it (QA's Test Banner sits at the bottom of pages),
and Statistics, whose resets wipe the wins, runs after the promo strip,
which needs one. Where one test leaves the screen the next needs, the next
carries on from it: Options → Contact Us, Play → abandon → relaunch.

The Daily cases come from FreeCell's TestRail list (docs/testrail/cases.py)
as written there, plus EXTRA_CASES for the steps that list has no case for.
The Daily flow runs in verifyDaily, its statistics reset in verifyStatistics
with the Solo one. The timer case (GP-12), the score case beside it (GP-25),
Show Status Bar (OP-10), Show Card Messages (OP-11, OP-12), Rank Strip (GP-26,
GP-08, GP-09), Auto Hint (OP-17, OP-18) and Maintain Card Spacing on a long
pile (OP-15, OP-16), all switched from the table's Options next to Rich
Features, run in verifyGamePlay. Each sits in its section after the cases
with its prefix and lower IDs.

Each test is one of:
  run  — a FreeCell port in tests/freecell_suite/<module>.py
  dev  — needs the dev build (QA code / Synthetic Win / QA page); skipped
         on prod, run by ``run_all.py --dev``
  skip — cannot run on this install at all; skipped with its reason

OP-07, GP-02, GP-08 and GP-09 are not in the case list: FreeCell has no
Use Hearts option and no stock pile to deal from. FreeCell's own GP-08 and
GP-09 (Rank Strip) take those two IDs instead.
"""
from __future__ import annotations

import importlib.util
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SUITE_CASES = os.path.join(ROOT, "docs", "testrail", "suite_cases.py")
FREECELL_CASES = os.path.join(ROOT, "docs", "testrail", "cases.py")

# The cases taken from FreeCell's TestRail list rather than the suite's.
FREECELL_ONLY = ("GP-08", "GP-09", "GP-12", "OP-10", "OP-11", "OP-12", "DY-01", "DY-02", "DY-03", "DY-05", "DY-07", "DY-10", "DY-11",
                 "DY-12", "DY-13", "DY-14", "RS-04", "RS-05", "RS-06")

# Steps FreeCell's TestRail list has no case for.
EXTRA_CASES = [
    {"id": "GP-25", "title": "Gameplay - Score counts when a card goes up to its foundation",
     "section": "FreeCell Solitaire Obj-C > Gameplay", "type": "Functional",
     "priority": "Medium",
     "steps": [("On a new deal, tap a card that can go up to its foundation.",
                "The card goes up and the score under the board rises from 0.")]},
    {"id": "GP-26", "title": "Gameplay - Rank Strip lights the cards of a touched rank or suit",
     "section": "FreeCell Solitaire Obj-C > Gameplay", "type": "Functional",
     "priority": "Medium",
     "steps": [("On a new deal, look at the strip under the cards (Rank Strip ships ON).",
                "It shows each rank still in play; A, 2 and 3, all up on Easy, are blank, "
                "with ♠♣ and ♥♦ at its ends."),
               ("Touch K on the strip.",
                "The four kings light up gold; no other card does."),
               ("Touch ♠ at the end of the strip.",
                "The next three spades to go up light up instead.")]},
    {"id": "OP-15", "title": "Options - Maintain Card Spacing ON folds a long pile under an arrow",
     "section": "FreeCell Solitaire Obj-C > Options", "type": "Functional",
     "priority": "Medium",
     "steps": [("On a table, build one column up to 13 cards with legal moves, then tap "
                "'tap to lower' so the pile no longer fits.",
                "Maintain Card Spacing ships ON: the top cards of the pile tuck under the "
                "next one and an arrow sits on top of it."),
               ("Tap the arrow.",
                "The pile spreads out: the arrow goes and every card shows its rank.")]},
    {"id": "OP-16", "title": "Options - Maintain Card Spacing OFF shows every card of a long pile",
     "section": "FreeCell Solitaire Obj-C > Options", "type": "Functional",
     "priority": "Medium",
     "steps": [("From the table's menu → options, turn Maintain Card Spacing off and go "
                "back to the same pile.",
                "No arrow; every card of the pile shows, squeezed closer together."),
               ("Turn it back on and go back to the table.",
                "The arrow is back on top of the pile.")]},
    {"id": "OP-17", "title": "Options - Auto Hint OFF leaves an idle table still",
     "section": "FreeCell Solitaire Obj-C > Options", "type": "Functional",
     "priority": "Medium",
     "steps": [("With Auto Hint at its default (OFF), make a move on a table and leave it "
                "alone for 15 s.",
                "Nothing on the table moves once the card has landed.")]},
    {"id": "OP-18", "title": "Options - Auto Hint ON pulses the next card after a few idle seconds",
     "section": "FreeCell Solitaire Obj-C > Options", "type": "Functional",
     "priority": "Medium",
     "steps": [("From the table's menu → options, turn Auto Hint on (it reads off), go back, "
                "make a move and leave the table alone.",
                "After a few seconds the next card to play pulses: it grows with a golden "
                "glow and shrinks back, over and over."),
               ("Tap the pulsing card, then turn Auto Hint back off.",
                "The card is played; Auto Hint reads off again.")]},
    {"id": "DY-15", "title": "Daily - A past date can be played and won",
     "section": "FreeCell Solitaire Obj-C > Daily", "type": "Functional",
     "priority": "Medium",
     "steps": [("Tap an unplayed past date, tap a card that can go up to its "
                "foundation, then win (Synthetic Win) and go back to Daily.",
                "A Daily table is dealt with a plain star; the timer starts and "
                "the score counts; the date carries a star.")]},
    {"id": "DY-16", "title": "Daily - Monthly score popup lists the games played",
     "section": "FreeCell Solitaire Obj-C > Daily", "type": "Functional",
     "priority": "Medium",
     "steps": [("Tap the monthly score on the calendar.",
                "A popup lists each played date's score, today's counted twice, "
                "and they add up to the monthly score. A tap closes it.")]},
]

DEV_REASON = "needs the dev build"
DAILY_DEV = "needs the dev build (Daily games are won with Synthetic Win)"

# (test, FreeCell module or None, kind, case ids, skip reason)
RUN_ORDER = [
    ("installFromTestFlight", None, "skip", ["FL-06"],
     "the dev build was installed by hand, not from TestFlight"),
    ("verifyFirstLaunch", "verifyFirstLaunch", "run",
     ["FL-04", "FL-05", "FL-02", "FL-03", "FL-01"], ""),
    ("verifyMainMenu", "verifyMainMenu", "run", ["MM-01"], ""),
    ("verifyOptions", "verifyOptions", "run",
     ["OP-01", "OP-03", "OP-04", "OP-05", "OP-06"], ""),
    ("verifyHelpShift", "verifyHelpShift", "run", ["HS-02"], ""),
    ("verifyHelpPage", "verifyHelpPage", "run", ["HP-01", "HP-02", "HP-03"], ""),
    ("verifyMoreGamesBtn", "verifyMoreGamesBtn", "run", ["MG-01", "MG-02", "MG-03"], ""),
    ("verifyFreeCellLogo", "verifyFreeCellLogo", "run",
     ["AB-01", "AB-03", "AB-04", "AB-05", "AB-06"], ""),
    ("openDebugTools", "openDebugTools", "dev", ["QA-02", "QA-03", "QA-04"],
     "needs the dev build (the prod build has no QA entry point)"),
    ("verifyPlay", "verifyPlay", "run", ["PL-01", "PL-02", "PL-03"], ""),
    ("verifyAbandonNo", "verifyAbandonNo", "run", ["PL-04"], ""),
    ("verifyRelaunch", "verifyRelaunch", "run", ["RL-01", "RL-02"], ""),
    ("verifyGamePlay", "verifyGamePlay", "run",
     ["GP-01", "GP-12", "GP-25", "GP-03", "GP-04", "GP-05", "GP-06",
      "GP-07", "GP-10", "GP-11", "OP-10", "OP-11", "OP-12", "GP-14", "GP-26", "GP-08",
      "GP-09", "OP-17", "OP-18", "OP-15", "OP-16"], ""),
    ("verifyVictory", "verifyVictory", "dev", ["VI-01", "VI-02", "VI-03", "VI-04"],
     "needs the dev build (Complete Game / Synthetic Win)"),
    ("verifyDifficultyLevels", "verifyDifficultyLevels", "dev",
     ["DL-01", "DL-02", "DL-03", "DL-04"],
     "needs the dev build (each level is completed with Synthetic Win)"),
    ("verifyChooseLook", "verifyChooseLook", "run",
     ["CL-01", "CL-03", "CL-04", "CL-05"], ""),
    ("verifyDaily", "verifyDaily", "run",
     ["DY-01", "DY-02", "DY-03", "DY-05", "DY-07", "DY-11", "DY-12", "DY-13",
      "DY-15", "DY-16", "DY-10", "DY-14"], ""),
    ("verifyMoreGamesIcons", "verifyMoreGamesIcons", "dev",
     ["PI-01", "PI-02", "PI-03", "PI-04", "PI-05", "PI-06"],
     "needs the dev build (the promo strip is drawn only after a won game)"),
    ("verifyStatistics", "verifyStatistics", "run",
     ["ST-01", "RS-06", "RS-04", "RS-05", "ST-03", "RS-03", "RS-01", "RS-02", "ST-04"], ""),
    ("verifyHelpShiftOnline", "verifyHelpShiftOnline", "run", ["HS-01"], ""),
    ("verifyAdFreeVersion", "verifyAdFreeVersion", "run",
     ["AF-02", "AF-01", "AF-03", "AF-04"], ""),
    ("submitFeedback", "submitFeedback", "run",
     ["FB-02", "FB-03", "FB-04", "FB-05", "FB-06"], ""),
    ("verifyAds", "verifyAds", "dev",
     ["AD-01", "AD-02", "AD-03", "AD-04", "AD-06", "AD-07"],
     "needs the dev build (QA page → Max: Adapters pins AppLovin)"),
    ("triggerAdPoints", "triggerAdPoints", "dev",
     ["TA-01", "TA-02", "TA-03", "TA-04", "TA-05",
      "TA-06", "TA-07", "TA-08", "TA-10", "TA-09"],
     "needs the dev build (prod serves live ads; some playables have no "
     "close control, so the run cannot stay unattended)"),
    ("visitLastScore", "visitLastScore", "dev",
     ["LS-01", "LS-02", "LS-03", "LS-04", "LS-05"],
     "needs the dev build (Last Score needs a win; prod has no Synthetic Win)"),
]

# Cases inside a run test that cannot run on the prod build.
DEV_CASES = OrderedDict((cid, DAILY_DEV) for cid in ("DY-12", "DY-13", "DY-15", "DY-16", "DY-14"))

# Left out of the main suite: each runs when it is named ("run_all.py
# verifyAds") or with --all.
STANDALONE = (
    "verifyChooseLook", "verifyAds", "triggerAdPoints", "visitLastScore",
    "verifyAdFreeVersion", "submitFeedback",
)

# The promo-strip test brings the phone online; Statistics, Contact Us online
# and the online standalone tests run after that transition, so the runner
# makes it even when the test itself is skipped.
ONLINE_FROM = "verifyMoreGamesIcons"

# Run cases that need the network. FL-02..05 also need a fresh install: the
# Terms card shows once per install and its policy pages load online.
ONLINE_CASES = (
    "FL-02", "FL-03", "FL-04", "FL-05", "HS-01",
    "AF-01", "AF-02", "AF-03", "AF-04",
    "FB-02", "FB-03", "FB-04", "FB-05", "FB-06",
)

# How the FreeCell build carries out a case, where its title alone does not say.
ADAPTED = OrderedDict([
    ("MM-01", "FreeCell's logo is the crown; the menu also has Daily"),
    ("PL-02", "FreeCell's five levels are Easy, Medium, Hard, Expert, Master"),
    ("RL-01", "after many force-quits FreeCell reopens a game in progress on its main "
              "menu instead of the table; then Play → Resume must bring back the exact board"),
    ("RL-02", "after many force-quits FreeCell reopens a game in progress on its main "
              "menu instead of the table; then Play → Resume must bring back the exact board"),
    ("GP-03", "undoes a card move — FreeCell has no stock deal"),
    ("AF-03", "lands on FreeCell's ad-free build"),
    ("AF-04", "FreeCell resumes on its main menu, not About — it does that after "
              "any trip to the background; still running is the resume proof"),
    ("MG-02", "the swiped list shows Card Games and Spiderette"),
    ("QA-02", "FreeCell has no Dev Panel button: QA off means no CONFIDENTIAL "
              "watermark on the menu and no 'reset alerts' control on About"),
    ("QA-03", "FreeCell unlocks QA with About → version line → 10 quick emblem taps → "
              "code 943010; 'reset alerts' shows bottom-right on About and "
              "CONFIDENTIAL on the menu"),
    ("QA-04", "FreeCell's code toggles: entering it again turns QA off"),
    ("VI-01", "Complete Game is the QA badge's Synthetic Win card (90% - 99%, WIN); "
              "it closes itself on the win"),
    ("DL-03", "FreeCell's levels after Easy are Medium, Hard, Expert, Master — "
              "this case plays Expert"),
    ("DL-04", "FreeCell's levels after Easy are Medium, Hard, Expert, Master — "
              "this case plays Master"),
    ("PI-01", "FreeCell's strip shows Spider, Solitaire, Sudoku 2, Card Games and "
              "Spiderette"),
    ("PI-05", "the strip's Spider icon opens Spider Solitaire in the App Store"),
    ("TA-04", "Complete Game is Synthetic Win; its card closes itself on the win"),
    ("TA-05", "FreeCell shows an ad on Victory → New even within 30 s of the Victory "
              "ad — its intended behaviour"),
    ("TA-06", "Complete Game is Synthetic Win; its card closes itself on the win"),
    ("AD-01", "FreeCell's Dev Panel is its QA page, opened from the menu's "
              "CONFIDENTIAL watermark; it offers Max: Adapters"),
    ("AD-02", "FreeCell's Max Debugger button is the QA page's Max: Adapters row"),
    ("AD-07", "FreeCell's Back ad closes onto the menu; the paused game is then "
              "resumed onto the table"),
    ("LS-03", "FreeCell's link opens the board of the level last won (Easy • Scores); "
              "Game Center's back arrow then shows Leaderboards"),
    ("DY-05", "the list is closed with a tap beside it; the level is left as it was"),
    ("DY-12", "plays the level the button shows, offline (the dev build deals Daily "
              "games without Wi-Fi); a card is first tapped up to its foundation — "
              "FreeCell scores only cards put up — so the timer starts and the score counts"),
    ("DY-14", "Daily statistics are brought to 0 / none before Daily opens (Reset Daily "
              "Statistics if needed); after today's and a past date's wins they read played "
              "2, won 2 and the higher score, in the totals and the level played"),
])

def _load_cases(path: str, name: str) -> list[dict]:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CASES


def _section(case: dict) -> str:
    return case["section"].split(" > ")[-1]


def _slot_in(cases: list[dict], own: list[dict]) -> list[dict]:
    """*own* added to *cases*, each after the last case of its section with a
    lower ID — of its own prefix when there is one, as Options also holds
    Contact Us (HS) — and at the end when its section is new."""
    out = list(cases)
    for case in own:
        before = [i for i, other in enumerate(out)
                  if _section(other) == _section(case) and other["id"] < case["id"]]
        before = [i for i in before if out[i]["id"][:2] == case["id"][:2]] or before
        out.insert(before[-1] + 1 if before else len(out), case)
    return out


CASES = _slot_in(_load_cases(SUITE_CASES, "suite_cases"),
                 [case for case in _load_cases(FREECELL_CASES, "freecell_cases")
                  if case["id"] in FREECELL_ONLY] + EXTRA_CASES)
TITLES = {case["id"]: case["title"] for case in CASES}
SECTIONS = {case["id"]: _section(case) for case in CASES}


def owner(cid: str) -> str:
    for name, _module, _kind, ids, _why in RUN_ORDER:
        if cid in ids:
            return name
    return ""


def entry(name: str):
    for item in RUN_ORDER:
        if item[0] == name:
            return item
    return None


def runnable_ids(ids: list[str]) -> list[str]:
    return [cid for cid in ids if cid not in DEV_CASES]


def counts() -> dict:
    executed = dev = skipped = 0
    for _name, _module, kind, ids, _why in RUN_ORDER:
        for cid in ids:
            if kind == "skip":
                skipped += 1
            elif kind == "dev" or cid in DEV_CASES:
                dev += 1
            else:
                executed += 1
    return {"run": executed, "dev build": dev, "skip": skipped}


def validate() -> dict:
    ids = [case["id"] for case in CASES]
    mapped: list[str] = []
    for name, module, kind, cids, why in RUN_ORDER:
        if kind == "run" and not module:
            raise ValueError(f"{name}: a run entry needs a FreeCell module")
        if kind in ("dev", "skip") and not why:
            raise ValueError(f"{name}: a {kind} entry needs a reason")
        mapped.extend(cids)
    dup = sorted({cid for cid in mapped if mapped.count(cid) > 1})
    if dup:
        raise ValueError(f"mapped twice: {dup}")
    unknown = sorted(set(mapped) - set(ids))
    if unknown:
        raise ValueError(f"not in the case list: {unknown}")
    unmapped = sorted(set(ids) - set(mapped))
    if unmapped:
        raise ValueError(f"cases with no parent: {unmapped}")
    missing = sorted(set(FREECELL_ONLY) - set(ids))
    if missing:
        raise ValueError(f"FreeCell cases not found in {FREECELL_CASES}: {missing}")
    stray = sorted((set(DEV_CASES) | set(ADAPTED)) - set(ids))
    if stray:
        raise ValueError(f"notes for unknown cases: {stray}")
    return counts()


if __name__ == "__main__":
    own = len(FREECELL_ONLY) + len(EXTRA_CASES)
    print(f"{len(CASES)} cases ({len(CASES) - own} suite, {own} from FreeCell's list): "
          f"{validate()}")
