"""Spider's regression suite, mapped onto the FreeCell prod build.

Case IDs, titles and sections are Spider's own (reference/spider/docs/
testrail/cases.py, identical to the Spider repo), with the game name swapped.
RUN_ORDER is Spider's tests/run_all.py TESTS (the main suite), then Spider's
six standalone tests (STANDALONE) in the order of Spider's report catalog.

FreeCell's Daily mode has no Spider counterpart, so its cases come from
FreeCell's own TestRail list (docs/testrail/cases.py) as written there,
plus EXTRA_CASES for the two steps that list has no case for. They run in
two FreeCell-only tests in the offline part of the main suite: verifyDaily
(the Daily flow) and resetDailyStats right after it.

Each Spider test is one of:
  run  — a FreeCell port in tests/spider_suite/<module>.py
  dev  — needs the dev build (QA code / Synthetic Win / QA page); skipped
         on prod, run by ``run_all.py --dev``
  skip — cannot run on this install at all; skipped with its reason

LATER lists the cases whose Spider behaviour FreeCell does not have. They
stay in the report and are filled in later against FreeCell's own gameplay.
"""
from __future__ import annotations

import importlib.util
import os
import re
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPIDER_CASES = os.path.join(ROOT, "reference", "spider", "docs", "testrail", "cases.py")
FREECELL_CASES = os.path.join(ROOT, "docs", "testrail", "cases.py")

# FreeCell's own cases with no Spider counterpart.
FREECELL_ONLY = ("DY-01", "DY-02", "DY-03", "DY-05", "DY-07", "DY-10", "DY-11",
                 "DY-12", "DY-13", "DY-14", "RS-04", "RS-05", "RS-06")

# Daily steps FreeCell's TestRail list has no case for.
EXTRA_CASES = [
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

# (Spider test, FreeCell module or None, kind, case ids, skip reason)
RUN_ORDER = [
    ("installFromTestFlight", None, "skip", ["FL-06"],
     "the dev build was installed by hand, not from TestFlight"),
    ("verifyFirstLaunch", "verifyFirstLaunch", "run",
     ["FL-01", "FL-02", "FL-03", "FL-04", "FL-05"], ""),
    ("verifyMainMenu", "verifyMainMenu", "run", ["MM-01"], ""),
    ("verifyStatsPage", "verifyStatsPage", "run", ["ST-01", "ST-03", "ST-04"], ""),
    ("verifyOptions", "verifyOptions", "run",
     ["OP-01", "OP-03", "OP-04", "OP-05", "OP-06", "OP-07"], ""),
    ("verifyHelpShift", "verifyHelpShift", "run", ["HS-02"], ""),
    ("verifyHelpPage", "verifyHelpPage", "run", ["HP-01", "HP-02", "HP-03"], ""),
    ("verifySpiderLogo", "verifyFreeCellLogo", "run",
     ["AB-01", "AB-03", "AB-04", "AB-05", "AB-06"], ""),
    ("verifyMoreGamesBtn", "verifyMoreGamesBtn", "run", ["MG-01", "MG-02", "MG-03"], ""),
    ("verifyPlay", "verifyPlay", "run", ["PL-01", "PL-02", "PL-03"], ""),
    ("verifyAbandonNo", "verifyAbandonNo", "run", ["PL-04"], ""),
    ("verifyRelaunch", "verifyRelaunch", "run", ["RL-01", "RL-02"], ""),
    ("openDebugTools", "openDebugTools", "dev", ["QA-02", "QA-03", "QA-04"],
     "needs the dev build (the prod build has no QA entry point)"),
    ("verifyGamePlay", "verifyGamePlay", "run",
     ["GP-01", "GP-02", "GP-03", "GP-04", "GP-05", "GP-06",
      "GP-07", "GP-08", "GP-09", "GP-10", "GP-11", "GP-14"], ""),
    ("verifyVictory", "verifyVictory", "dev", ["VI-01", "VI-02", "VI-03", "VI-04"],
     "needs the dev build (Complete Game / Synthetic Win)"),
    ("verifyDifficultyLevels", "verifyDifficultyLevels", "dev",
     ["DL-01", "DL-02", "DL-03", "DL-04"],
     "needs the dev build (each level is completed with Synthetic Win)"),
    ("verifyDaily", "verifyDaily", "run",
     ["DY-01", "DY-02", "DY-03", "DY-05", "DY-07", "DY-11", "DY-12", "DY-13",
      "DY-15", "DY-16", "DY-10", "DY-14"], ""),
    ("resetDailyStats", "resetDailyStats", "run", ["RS-06", "RS-04", "RS-05"], ""),
    ("verifyMoreGamesIcons", "verifyMoreGamesIcons", "dev",
     ["PI-01", "PI-02", "PI-03", "PI-04", "PI-05", "PI-06"],
     "needs the dev build (the promo strip is drawn only after a won game)"),
    ("verifyResetCancelled", "verifyResetCancelled", "run", ["RS-03"], ""),
    ("resetStats", "resetStats", "run", ["RS-01", "RS-02"], ""),
    ("verifyHelpShiftOnline", "verifyHelpShiftOnline", "run", ["HS-01"], ""),
    ("verifyChooseLook", "verifyChooseLook", "run",
     ["CL-01", "CL-03", "CL-04", "CL-05"], ""),
    ("verifyAds", "verifyAds", "dev",
     ["AD-01", "AD-02", "AD-03", "AD-04", "AD-06", "AD-07"],
     "needs the dev build (QA page → Max: Adapters pins AppLovin)"),
    ("triggerAdPoints", "triggerAdPoints", "dev",
     ["TA-01", "TA-02", "TA-03", "TA-04", "TA-05",
      "TA-06", "TA-07", "TA-08", "TA-09", "TA-10"],
     "needs the dev build (prod serves live ads; some playables have no "
     "close control, so the run cannot stay unattended)"),
    ("visitLastScore", "visitLastScore", "dev",
     ["LS-01", "LS-02", "LS-03", "LS-04", "LS-05"],
     "needs the dev build (Last Score needs a win; prod has no Synthetic Win)"),
    ("verifyAdFreeVersion", "verifyAdFreeVersion", "run",
     ["AF-01", "AF-02", "AF-03", "AF-04"], ""),
    ("submitFeedback", "submitFeedback", "run",
     ["FB-02", "FB-03", "FB-04", "FB-05", "FB-06"], ""),
]

# Cases inside a run test that cannot run on the prod build.
DEV_CASES = OrderedDict((cid, DAILY_DEV) for cid in ("DY-12", "DY-13", "DY-15", "DY-16", "DY-14"))

# Spider's run_all.py leaves these out of TESTS and runs each only when it is
# named ("run_all.py verifyAds"); see the note above Spider's TESTS.
STANDALONE = (
    "verifyChooseLook", "verifyAds", "triggerAdPoints", "visitLastScore",
    "verifyAdFreeVersion", "submitFeedback",
)

# Spider's promo-strip test brings the phone online; the reset tests and
# Contact Us online run after that transition, so the runner makes it even
# when the test itself is skipped.
ONLINE_FROM = "verifyMoreGamesIcons"

# Run cases that need the network. FL-02..05 also need a fresh install: the
# Terms card shows once per install and its policy pages load online.
ONLINE_CASES = (
    "FL-02", "FL-03", "FL-04", "FL-05", "HS-01",
    "AF-01", "AF-02", "AF-03", "AF-04",
    "FB-02", "FB-03", "FB-04", "FB-05", "FB-06",
)

# Spider behaviour FreeCell does not have — filled in later.
LATER = OrderedDict([
    ("OP-07", "FreeCell difference — FreeCell's Options have no Use Hearts"),
    ("GP-02", "FreeCell difference — FreeCell has no stock pile to deal from"),
    ("GP-08", "FreeCell difference — FreeCell has no Use Hearts"),
    ("GP-09", "FreeCell difference — FreeCell has no Use Hearts"),
])

# Where the FreeCell build words a step differently from Spider.
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
              "Spider's Bold is Expert here"),
    ("DL-04", "FreeCell's levels after Easy are Medium, Hard, Expert, Master — "
              "Spider's Expert is Master here"),
    ("PI-01", "FreeCell's strip shows Spider where Spider's shows FreeCell"),
    ("PI-05", "FreeCell's strip has the Spider icon in place of FreeCell; it opens "
              "Spider Solitaire"),
    ("TA-04", "Complete Game is Synthetic Win; its card closes itself on the win"),
    ("TA-05", "FreeCell shows an ad on Victory → New even within 30 s of the Victory "
              "ad — its intended behaviour, where Spider shows none"),
    ("TA-06", "Complete Game is Synthetic Win; its card closes itself on the win"),
    ("AD-01", "FreeCell's Dev Panel is its QA page, opened from the menu's "
              "CONFIDENTIAL watermark; it offers Max: Adapters"),
    ("AD-02", "FreeCell's Max Debugger button is the QA page's Max: Adapters row"),
    ("AD-07", "FreeCell's Back ad closes onto the menu; the paused game is resumed "
              "onto the table, as Spider does when its ad closes off the table"),
    ("LS-03", "FreeCell's link opens the board of the level last won (Easy • Scores); "
              "Game Center's back arrow then shows Leaderboards"),
    ("DY-05", "the list is closed with a tap beside it; the level is left as it was"),
    ("DY-12", "plays the level the button shows, offline (the dev build deals Daily "
              "games without Wi-Fi); a card is first tapped up to its foundation — "
              "FreeCell scores only cards put up — so the timer starts and the score counts"),
    ("DY-14", "checked after today's and a past date's wins: games won goes up by both "
              "and the best score takes the higher"),
])

# FreeCell wording where swapping the game name is not enough.
TITLE_OVERRIDES = {
    "MG-02": "More Games - Swipe reveals Card Games and Spiderette",
    "AF-04": "Ad-free - Status-bar back resumes FreeCell",
    "QA-03": "QA - Ten emblem taps and the code turn QA on",
    "QA-04": "QA - The code again turns QA off",
    "DL-03": "Difficulty - Expert starts and can be completed",
    "DL-04": "Difficulty - Master starts and can be completed",
    "PI-05": "Promo icons - Spider opens Spider Solitaire",
    "TA-05": "Ads - New within 30s of the Victory ad also shows an ad",
}


def _load_cases(path: str, name: str) -> list[dict]:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CASES


def _freecell(text: str) -> str:
    text = text.replace("Spider Solitaire Unity", "FreeCell Solitaire")
    return re.sub(r"\bSpider\b", "FreeCell", text)


CASES = [
    dict(case,
         title=TITLE_OVERRIDES.get(case["id"]) or _freecell(case["title"]),
         section=_freecell(case["section"]))
    for case in _load_cases(SPIDER_CASES, "spider_cases")
] + [case for case in _load_cases(FREECELL_CASES, "freecell_cases")
     if case["id"] in FREECELL_ONLY] + EXTRA_CASES
TITLES = {case["id"]: case["title"] for case in CASES}
SECTIONS = {case["id"]: case["section"].split(" > ")[-1] for case in CASES}


def owner(cid: str) -> str:
    for spider, _module, _kind, ids, _why in RUN_ORDER:
        if cid in ids:
            return spider
    return ""


def entry(spider: str):
    for item in RUN_ORDER:
        if item[0] == spider:
            return item
    return None


def runnable_ids(ids: list[str]) -> list[str]:
    return [cid for cid in ids if cid not in LATER and cid not in DEV_CASES]


def counts() -> dict:
    executed = dev = later = skipped = 0
    for _spider, _module, kind, ids, _why in RUN_ORDER:
        for cid in ids:
            if cid in LATER:
                later += 1
            elif kind == "skip":
                skipped += 1
            elif kind == "dev" or cid in DEV_CASES:
                dev += 1
            else:
                executed += 1
    return {"run": executed, "dev build": dev, "skip": skipped, "later": later}


def validate() -> dict:
    ids = [case["id"] for case in CASES]
    mapped: list[str] = []
    for spider, module, kind, cids, why in RUN_ORDER:
        if kind == "run" and not module:
            raise ValueError(f"{spider}: a run entry needs a FreeCell module")
        if kind in ("dev", "skip") and not why:
            raise ValueError(f"{spider}: a {kind} entry needs a reason")
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
    stray = sorted((set(LATER) | set(DEV_CASES) | set(ADAPTED)) - set(ids))
    if stray:
        raise ValueError(f"notes for unknown cases: {stray}")
    return counts()


if __name__ == "__main__":
    own = len(FREECELL_ONLY) + len(EXTRA_CASES)
    print(f"{len(CASES)} cases ({len(CASES) - own} Spider, {own} FreeCell Daily): "
          f"{validate()}")
