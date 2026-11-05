# FreeCell Solitaire Automation

Functional regression for FingerArts FreeCell on a real iPhone:

- bundle ID: `com.fingerarts.FreeCell`
- QA code: `943010` (About → version line → 10 emblem taps → code)
- phone: iPhone 15 Pro Max, UDID `00008130-00010D283A31001C`, iOS 27.2
- last full run: dev build 7.42.1 (266)
- driver: WebDriverAgent over USB (`scripts/wda.sh`), taps and shots over HTTP

The live suite is `tests/freecell_suite/`. Every crop and assertion is from
FreeCell on this phone. Case IDs, titles and the run order live in
`tests/freecell_suite/catalog.py`.

## Current status

169 cases: 82 run on any build, 86 need the dev build (QA, Synthetic Win,
Last Score, Daily wins), 1 skip (FL-06, TestFlight). `--prod` leaves the
86 out. DY-02 and DY-03 skip unless FreeCell was deleted and reinstalled
without opening it.

Ads (`verifyAds`, `triggerAdPoints`), Device Setup, and `openDebugTools`
are parked: they stay out of `--all` and `--main` and only run when named.

`--main` is the live presentation run. Last Score sits after the promo
strip in that same online session, before Statistics reset, and reads the
won game's current / rank / best. Daily is offline on the dev build: no
interstitial wait after a win.

Every Victory screen (Solo, each difficulty, Daily, Last Score) checks
**current / rank / best** for score, time and moves (Solo also has run).
Scores are read by digit shape first; Vision lookalikes and split comma
groups (`77,90₴` for 77,902, `З4‚З69х2` for 34,369 × 2) are glued so a
number that is on screen does not fail the case.

WDA no longer waits for FreeCell to go idle after a tap or swipe. FreeCell
sometimes never reports idle (one swipe in nine on Options), and XCTest
then holds the reply 15–30 s. A FreeCell session turns those waits off and
pauses 1 s after a tap / 2 s after a swipe instead. Settings keeps WDA's
own waits, so the radio switches still settle. Gestures time out at 60 s
and a call over 10 s is logged.

Other things that used to fail a clean run:

- More Games is tapped on its label, not the centre of its crop (that
  centre is felt above the button).
- RS-03 compares Statistics below the header, where iOS notification
  banners drop in, and looks again after 6 s if the pages still differ.
- The phone locking itself mid-run (Auto-Lock) made every launch after it
  answer 500, so every later test failed. The run now sets Auto-Lock to
  Never in Settings before it starts, and a launch on a locked phone wakes
  it, or prints "Manual effort required" and waits for a hand unlock.
- An alert FreeCell did not raise (an Apple account notice) is never
  answered. The run prints "Manual effort required" and waits for you.
- Victory and Daily-popup scores are read by digit shape first
  (`assets/victory_digit_0.png` … `9.png`). Vision lookalikes and a split
  thousands comma are glued (`ocr.score` / `ocr.same`) so a number that is
  on screen is not a fail.
- A Statistics best score must agree with those shapes; if it does not,
  more reads of the line vote (Vision has dropped trailing digits).

## One command (live console)

Phone plugged in, unlocked and online:

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation && ./scripts/regression.sh --pick
```

That lists every module numbered, plus **Run full regression** and **Run main suite only**. Type the number and press Enter. Same as before, no picker:

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation && ./scripts/regression.sh
```

`scripts/regression.sh` starts WDA (re-signing it if the 7-day profile is
due), keeps the Mac awake, and runs `tests/freecell_suite/run_all.py --dev
--all` through `scripts/present_regression.py`. The console lists each
test's cases, then every case as it starts, the steps it takes, and PASS /
FAIL / SKIP with its time. It writes `log/regression_<time>.log` and opens
`log/reports/<version>_<build>/FreeCell_<version>_<build>_<scope>_<time>.html`
(for example `log/reports/7.42.1_266/FreeCell_7.42.1_266_verifyAds_2026-11-02_1512.html`).
A named module's report holds only that module's cases. The same build
reuses that folder; a new version or build number gets a new folder.
`log/freecell_suite_report.html` is a link to whichever report was written
last. Hover the browser tab for version, build, module, result and time.

A failed case does not stop the rest of that module or the suite. After
every case has run — and before the report — only the failed cases are
tried once more. A first-run pass is kept and not run again. A case that
passes there is a plain pass in the report; its first failure stays in
`log/freecell_suite_results.json` (`first_failure`). `--no-rerun` turns
that off.

| Option | Runs |
| --- | --- |
| `--pick` | numbered list of every module; type a number (1 = full, 2 = main) |
| `--main` | main suite only, no standalone tests (about 40 minutes) |
| `verifyGamePlay verifyDaily` | only the named tests |
| `--prod` | the App Store build (leaves out the 86 dev-build cases) |
| `--no-open` | does not open the report at the end |
| `--no-rerun` | does not rerun failed tests |
| `stop` / `stop --now` | stop a run in another window; `--now` leaves the network as it is |

Ctrl-C stops the run; the runner still turns the network back on. From
another terminal: `./scripts/regression.sh stop`. Agent-launched runs need
`FORCE_COLOR=1` for the coloured console.

## The suite

Order is in `catalog.py`. Each screen is visited once where the data
allows: first launch first (a fresh install's Terms card), the middle
offline so no interstitial covers a deal, QA unlocked before the wins,
More Games before QA (the Test Banner sits at the bottom of pages), and
Statistics after the promo strip, which needs a win.

| When | Tests |
| --- | --- |
| First, before FreeCell opens | Device setup: Auto-Lock Never (DS-01), Do Not Disturb on (DS-02) — each is set if found wrong |
| Online, then offline | First launch (policy links only when the Terms card is up), menu, Options, Help, More Games, About |
| Offline | Play, abandon, relaunch, GamePlay, Victory (incl. current / rank / best), difficulty levels, Daily |
| Online from the promo strip | More Games icons, Last Score (same session), Statistics, Contact Us online, then Ad-free and Feedback |

verifyGamePlay holds the table cases: a legal move, the timer (GP-12) and
score (GP-25), undo / hint / cells / foundations, Show Status Bar
(OP-10), Show Card Messages (OP-11, OP-12), Rank Strip (GP-26, GP-08,
GP-09), Auto Hint (OP-17, OP-18), and Maintain Card Spacing on a 13-card
pile (OP-15, OP-16). Rank Strip and the Options next to Rich Features are
switched from the table's menu → options on the same deal.

verifyDaily opens the calendar, checks the tips and level list, then on
the dev build: Standard Medium today and a past date at 15–30, today again
at 90–99 (Victory +N), that past date at 00–15 (No improvement), table
Replay / No score recorded, then Relaxed Easy today and a past date at
90–99 only. Each Victory also checks current / rank / best. DY-14 is Daily
statistics for those six wins (Medium 4, Easy 2). Offline Daily does not
wait for an interstitial after a win.

verifyStatistics opens Stats, declines then confirms the Daily reset
(RS-06, RS-04, RS-05), then the Solo reset (RS-03, RS-01, RS-02). Those
resets wipe the wins, so this test runs last among the ones that need
them.

A leftover table is never a lost app: tap Back and continue. Matching,
shots, taps and swipes go through WDA HTTP.

Without `--all` or a name, the standalone tests stay out:
`verifyChooseLook`, `verifyAdFreeVersion`, `submitFeedback`. Ads and
`triggerAdPoints` are parked (named run only).

## Setup

```bash
./scripts/setup.sh
export DEVICE_UDID=00008130-00010D283A31001C
./scripts/wda.sh          # phone UNLOCKED and online; it exits once WDA answers
./.venv/bin/python tests/connect_check.py
```

The runner itself:

```bash
./.venv/bin/python -u tests/freecell_suite/run_all.py --dev --all
./.venv/bin/python -u tests/freecell_suite/run_all.py --offline
./.venv/bin/python -u tests/freecell_suite/run_all.py verifyPlay verifyGamePlay
```

`SKIP_OFFLINE=1` leaves the network up (ads may interrupt).

FreeCell is never on screen while the network is up: an ad it loads then
shows later in the offline run. Going online closes FreeCell first (Home,
then kill). Do not restart WDA after the suite goes offline. The run ends
online, FreeCell already closed.

A Mail account on the phone is needed for the Feedback cases.

## WDA

The signed runner for this phone is in [`wda/`](wda/README.md).
`scripts/wda.sh` finds it — do not point `WDA_PRODUCTS` at `/tmp`. Its
profile comes from a free Apple ID and lasts 7 days. `wda.sh` re-signs
into `log/wda-build` when under a day is left; `./scripts/wda.sh renew`
forces it. Xcode must be signed in to that Apple ID.

After a re-sign, iOS may refuse the runner until it is trusted again:
Settings → General → VPN & Device Management → the Apple Development
entry → Verify App / Trust, with the phone online.

```bash
./scripts/wda.sh stop     # only when asked; a finished run leaves WDA up
```

## Capture-first workflow

Every FreeCell asset is cropped from this phone (`1290×2796`). Capture,
then crop only names listed in `scripts/crop_suite_assets.py` (existing
assets are never overwritten):

```bash
./.venv/bin/python tests/capture_walkthrough.py
./.venv/bin/python scripts/crop_suite_assets.py
./.venv/bin/python tests/verify_assets.py
```

## Obj-C baselines

`baselines/` holds 43 screenshots of the Obj-C build, FreeCell 7.42.5
(279), on this iPhone in portrait, plus a learned motion mask
(`<Name>.volatile.png`) for each animated screen. The Unity port is
compared against them. **Never re-baseline them to a Unity build** — a
large diff is the finding. `baselines/MANIFEST.md` lists how each screen
is reached.

They only need re-shooting if the Obj-C reference itself is lost. Each
pass needs a fresh install, because phase A reads the untouched state:

```bash
DEVICE_UDID=00008130-00010D283A31001C ./.venv/bin/python -u tests/capture_baselines.py --out log/objc_pass2
./.venv/bin/python scripts/update_baselines.py --src log/objc_pass2 --also log/objc_baselines --replace
./.venv/bin/python tests/compare_unity.py --dir log/objc_baselines
```

To compare a Unity build, capture the same screen names into
`log/unity/<build>/`, then:

```bash
./.venv/bin/python tests/compare_unity.py --dir log/unity/<build>
./.venv/bin/python scripts/gen_report.py
```

A pixel counts as changed when any colour channel moves more than 32. A
screen fails when the changed share passes its `max_diff`, or one changed
blob passes 2500 px². Read the diff images in `log/diff/<build>/`, not
just the table.

## Other docs

| File | What it is |
| --- | --- |
| [`docs/OBSERVED_FREECELL.md`](docs/OBSERVED_FREECELL.md) | Screens and behaviour seen on the phone |
| [`docs/testrail/README.md`](docs/testrail/README.md) | TestRail export (titles and steps) |
| [`docs/CAPTURE_MANIFEST.md`](docs/CAPTURE_MANIFEST.md) | Capture list for new crops |
| [`wda/README.md`](wda/README.md) | Signed WDA, renew, trust |
| [`baselines/MANIFEST.md`](baselines/MANIFEST.md) | How each Obj-C baseline screen is reached |
