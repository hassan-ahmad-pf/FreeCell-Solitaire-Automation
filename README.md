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

126 cases in 26 tests: 82 run on any build, 43 need the dev build (QA,
Synthetic Win, ads, Last Score), 1 skip (FL-06, TestFlight). `--prod` leaves
the 43 out. DY-02 and DY-03 skip unless FreeCell was deleted and reinstalled
without opening it.

A full `--all` run on this phone is about 95 minutes (GamePlay ~18 min, the
ad trigger points ~29 min). `--main` is about 40 minutes: it leaves out the
six standalone tests (Choose Look, Ad-free, Feedback, Ads, Ad trigger
points, Last Score).

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
- Victory scores are read by digit shape (`assets/victory_digit_0.png` …
  `9.png`). Vision reads this font's 2 as 3.
- A Statistics best score must agree with those shapes; if it does not,
  more reads of the line vote (Vision has dropped trailing digits).

## One command (live console)

Phone plugged in, unlocked and online:

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation && ./scripts/regression.sh
```

`scripts/regression.sh` starts WDA (re-signing it if the 7-day profile is
due), keeps the Mac awake, and runs `tests/freecell_suite/run_all.py --dev
--all` through `scripts/present_regression.py`. The console lists each
test's cases, then every case as it starts, the steps it takes, and PASS /
FAIL / SKIP with its time. It writes `log/regression_<time>.log` and opens
`log/freecell_suite_report.html`.

Failed tests run once more by default, with the network as on the first
run. A case that passes there is a plain pass in the report; its first
failure stays in `log/freecell_suite_results.json` (`first_failure`).
`--no-rerun` turns that off.

| Option | Runs |
| --- | --- |
| `--main` | main suite only, no standalone tests (about 40 minutes) |
| `verifyGamePlay verifyDaily` | only the named tests |
| `--prod` | the App Store build (leaves out the 43 dev-build cases) |
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
| Offline | QA unlock, Play, abandon, relaunch, GamePlay, Victory, difficulty levels, Daily |
| Online from the promo strip | More Games icons, Statistics, Contact Us online, then the standalone tests |

verifyGamePlay holds the table cases: a legal move, the timer (GP-12) and
score (GP-25), undo / hint / cells / foundations, Show Status Bar
(OP-10), Show Card Messages (OP-11, OP-12), Rank Strip (GP-26, GP-08,
GP-09), Auto Hint (OP-17, OP-18), and Maintain Card Spacing on a 13-card
pile (OP-15, OP-16). Rank Strip and the Options next to Rich Features are
switched from the table's menu → options on the same deal.

verifyDaily (DY-01 … DY-16) opens the calendar, checks the tips and level
list, plays today and a past date with Synthetic Win, reads the monthly
score popup, and checks Daily statistics. DY-12 … DY-16 and DY-14 need the
dev build.

verifyStatistics opens Stats, declines then confirms the Daily reset
(RS-06, RS-04, RS-05), then the Solo reset (RS-03, RS-01, RS-02). Those
resets wipe the wins, so this test runs last among the ones that need
them.

A leftover table is never a lost app: tap Back and continue. Matching,
shots, taps and swipes go through WDA HTTP.

Without `--all` or a name, the six standalone tests stay out:
`verifyChooseLook`, `verifyAdFreeVersion`, `submitFeedback`, `verifyAds`,
`triggerAdPoints`, `visitLastScore`.

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
