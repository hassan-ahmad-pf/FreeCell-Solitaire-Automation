# TestRail cases — FreeCell Obj-C build

Cases a **person** can run on the phone, one case per behaviour, written as
Tap / Wait / Check. The same list drives the automated suite: each case id is
owned by one test in [`catalog.py`](catalog.py), and that test records the
case's own pass / fail (`caselog.py`).

**147 cases: 134 automated offline, 13 online - later.** Behaviour is as
observed on the device ([`../OBSERVED_FREECELL.md`](../OBSERVED_FREECELL.md)).

| File | Role |
|---|---|
| [`cases.py`](cases.py) | Source of truth for titles and steps — edit this |
| [`catalog.py`](catalog.py) | Which test automates which case; the online-later list |
| [`freecell_objc_testrail.csv`](freecell_objc_testrail.csv) | TestRail import (one row per step) |
| [`freecell_objc_cases.csv`](freecell_objc_cases.csv) | One row per case — browse or import into Google Sheets |
| [`freecell_objc_cases.xlsx`](freecell_objc_cases.xlsx) | Same data, two tabs (`Cases` + `TestRail steps`) |
| [`../../scripts/export_testrail_csv.py`](../../scripts/export_testrail_csv.py) | Regenerates the CSV / xlsx |

```bash
./.venv/bin/python scripts/export_testrail_csv.py
```

## The build under test

Install the **dev build** fresh before every run, and leave it unopened:

- The win cases (Victory, the difficulty levels, the statistics after a win)
  use the QA code on About and its Synthetic Win. The App Store release has no
  QA code, so it cannot run them.
- The fresh-install cases need the first launch: Terms & Conditions, the
  tracking prompt, the empty statistics, the Daily tips, the Last Score
  notice, and the first-game prompts.

## Automation column

| Value | Meaning |
|---|---|
| Automated | A test in `catalog.py` runs it offline and records its result |
| Online - later | Needs the network while FreeCell is on screen: App Store pages, Game Center, online support, and every Daily table (Daily games are dealt only online) |
| Manual | Not owned by any test (none at the moment) |

## Open in Google Sheets

1. Open [https://sheets.google.com](https://sheets.google.com) and sign in.
2. **File → Import → Upload** and choose
   [`freecell_objc_cases.xlsx`](freecell_objc_cases.xlsx).
3. Import location: **Create new spreadsheet**.
4. **Share → Anyone with the link → Viewer** (or Editor) and copy the URL.

## Import into TestRail

1. Open the project → **Test Cases** → **Import** → **Import from CSV**.
2. Upload `freecell_objc_testrail.csv`.
3. Encoding **UTF-8**, delimiter **comma**, start row **1**, header row **on**.
4. Template: **Test Case (Steps)**. Row layout: **Test cases use multiple
   rows**. Column that detects a new case: **Title**.

| CSV column | TestRail field |
|---|---|
| Title | Title |
| Section Hierarchy | Section Hierarchy |
| Type | Type |
| Priority | Priority |
| Step | Steps (Step) |
| Expected Result | Steps (Expected Result) |
| Case ID | custom field, or skip |
| Automation | custom field, or skip |

`Section Hierarchy` uses `>` (`FreeCell Solitaire Obj-C > Gameplay`).
TestRail creates those folders on import.
