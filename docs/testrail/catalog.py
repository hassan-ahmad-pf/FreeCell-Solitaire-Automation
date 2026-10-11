"""Which test automates which TestRail case.

Every case in cases.py is either owned by exactly one test here, or listed
in ONLINE_LATER (it needs the network with FreeCell on screen, which the
offline suite never allows). Screenshots are not listed: each test attaches
them to its own cases at run time through caselog.

    ./.venv/bin/python docs/testrail/catalog.py
"""
from collections import OrderedDict

CATALOG = OrderedDict([
    ("verifyFirstLaunch", ["FL-02", "FL-03", "FL-04", "FL-05"]),
    ("verifyMainMenu", ["MM-01", "FL-01"]),
    ("verifyStats", ["ST-01", "ST-02", "ST-03", "ST-04", "ST-05", "ST-06"]),
    ("verifyLastScoreNotice", ["LS-01"]),
    ("verifyDaily", ["DY-01", "DY-02", "DY-03", "DY-04", "DY-05", "DY-06",
                     "DY-07", "DY-08", "DY-09", "DY-10", "DY-11"]),
    ("verifyFirstGame", ["GP-13", "MM-02"]),
    ("verifyPromoIcons", ["PI-01"]),
    ("verifyOptions", ["OP-01", "OP-02", "OP-03", "OP-04", "OP-05", "OP-06",
                       "OP-07", "OP-08", "OP-09", "OP-13", "OP-14", "HS-02"]),
    ("verifyHelp", ["HP-01", "HP-02", "HP-03", "HP-04"]),
    ("verifyAbout", ["AB-01", "AB-02", "AB-03", "AB-04", "AB-05", "AB-06",
                     "AB-07", "AB-08", "AB-09",
                     "FQ-01", "FQ-02", "FQ-03", "FQ-04"]),
    ("verifyAdFreePrompt", ["AF-01", "AF-02"]),
    ("submitFeedback", ["FB-01", "FB-02", "FB-03", "FB-04", "FB-05", "FB-06"]),
    ("verifyMoreGames", ["MG-01", "MG-02", "MG-03"]),
    ("verifyChooseLook", ["CL-01", "CL-02", "CL-03", "CL-04", "CL-05",
                          "CL-06", "CL-07"]),
    ("verifyPlay", ["PL-01", "PL-02", "PL-03", "PL-04", "PL-05", "PL-06",
                    "PL-07"]),
    ("verifyGamePlay", ["GP-01", "GP-02", "GP-03", "GP-04", "GP-05", "GP-06",
                        "GP-07", "GP-12", "GP-14", "GP-15", "GP-16", "GP-17",
                        "GP-18", "GP-19", "GP-23", "GP-24"]),
    ("verifyTableOptions", ["OP-10", "OP-11", "OP-12", "GP-20"]),
    ("verifyRotationLock", ["GP-21", "GP-22"]),
    ("verifyRichFeaturesOn", ["GP-11"]),
    ("verifyRichFeaturesOff", ["GP-10"]),
    ("verifyRankStrip", ["GP-08", "GP-09"]),
    ("verifyRelaunch", ["RL-01", "RL-02"]),
    ("verify_qa_victory", ["QA-01", "QA-02", "QA-03", "VI-01", "VI-02",
                           "VI-03", "VI-04", "VI-05", "VI-06", "VI-07"]),
    ("verifyDifficultyLevels", ["DL-01", "DL-02", "DL-03", "DL-04"]),
    ("verifyLastScore", ["LS-02", "LS-03", "LS-06"]),
    ("verifySoloStats", ["ST-07"]),
    ("verifyQaOff", ["QA-04"]),
    ("verifyResetCancelled", ["RS-03", "RS-06"]),
    ("resetStats", ["RS-01", "RS-02", "RS-04", "RS-05"]),
])

ONLINE_LATER = OrderedDict([
    ("HS-01", "PeopleFun Support only loads online"),
    ("AF-03", "the App Store page needs the network"),
    ("AF-04", "follows AF-03 back from the App Store"),
    ("PI-02", "the App Store page needs the network"),
    ("PI-03", "the App Store page needs the network"),
    ("PI-04", "the App Store page needs the network"),
    ("PI-05", "the App Store page needs the network"),
    ("PI-06", "the App Store page needs the network"),
    ("LS-04", "Game Center needs the network and an Apple ID"),
    ("LS-05", "Game Center needs the network and an Apple ID"),
    ("DY-12", "Daily games are dealt only online"),
    ("DY-13", "needs a Daily table, which needs the network"),
    ("DY-14", "needs a Daily win, which needs the network"),
])

# Tests that need the dev build: the QA code does nothing on the App Store
# build, so there is no Synthetic Win. run_all.py --prod leaves them out.
DEV_BUILD = OrderedDict([
    ("verify_qa_victory", "needs the QA code and Synthetic Win (dev build)"),
    ("verifyDifficultyLevels", "needs a win via QA Synthetic Win (dev build)"),
    ("verifyLastScore", "needs a win via QA Synthetic Win (dev build)"),
    ("verifySoloStats", "needs a win via QA Synthetic Win (dev build)"),
    ("verifyQaOff", "needs the QA code (dev build)"),
    ("verifyResetCancelled", "needs a Solo score from a QA win (dev build)"),
])


def owner(cid):
    """The test that automates *cid*, or None."""
    for test, ids in CATALOG.items():
        if cid in ids:
            return test
    return None


def automation(cid):
    """The TestRail Automation column for *cid*."""
    if cid in ONLINE_LATER:
        return "Online - later"
    return "Automated" if owner(cid) else "Manual"


def validate(cases):
    """Raise unless every case is owned exactly once and every id exists."""
    known = {case["id"] for case in cases}
    seen = {}
    for test, ids in CATALOG.items():
        for cid in ids:
            if cid not in known:
                raise ValueError(f"{test} lists unknown case {cid}")
            if cid in seen:
                raise ValueError(f"{cid} is owned by {seen[cid]} and {test}")
            seen[cid] = test
    for cid in ONLINE_LATER:
        if cid not in known:
            raise ValueError(f"ONLINE_LATER lists unknown case {cid}")
        if cid in seen:
            raise ValueError(f"{cid} is both automated ({seen[cid]}) and "
                             "online-later")
    orphans = sorted(known - set(seen) - set(ONLINE_LATER))
    if orphans:
        raise ValueError(f"cases with no owner: {orphans}")
    stray = [test for test in DEV_BUILD if test not in CATALOG]
    if stray:
        raise ValueError(f"DEV_BUILD lists tests not in CATALOG: {stray}")
    return len(seen), len(ONLINE_LATER)


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cases import CASES

    automated, later = validate(CASES)
    print(f"{len(CASES)} cases: {automated} automated, {later} online - later")
