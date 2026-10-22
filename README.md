# FreeCell Solitaire Automation

Standalone Objective-C UI automation for FingerArts FreeCell:

- bundle ID: `com.fingerarts.FreeCell`
- QA code: `943010`
- target: a real USB-connected iPhone through WebDriverAgent and Airtest

All code uses FreeCell captures and FreeCell-specific assertions.

## Current status

The signed WDA for this phone lives in [`wda/`](wda/README.md). `scripts/wda.sh`
finds it automatically — do not point `WDA_PRODUCTS` at `/tmp`. Its profile
comes from a free Apple ID and lasts 7 days, so `wda.sh` re-signs WDA into
`log/wda-build` by itself when under a day is left (Xcode must be signed in
to that Apple ID); `./scripts/wda.sh renew` forces it.

## One command (live console)

With the phone plugged in, unlocked and online, paste into Terminal:

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation && ./scripts/regression.sh
```

`scripts/regression.sh` starts WDA (re-signing it if due), keeps the Mac
awake and runs the FreeCell suite on the dev build, standalone tests
included (about 80 minutes). The console shows the plan with each test's
time on the last run, every case as it starts and its PASS / FAIL / SKIP
with its time and note, and a status bar with the elapsed time, the current
case, pass and fail counts and the time left. It ends with a RESULT line,
opens the HTML report and keeps a plain log in `log/regression_<time>.log`.

If any case fails, the runner writes the report, runs each failed test once
more (with the network as the first run had it) and writes the report again.
A failed case that passes on the rerun is a plain pass in the report; its
first failure stays only in `log/freecell_suite_results.json`
(`first_failure`) and the console log. One that fails again, or cannot
rerun (a fresh-install case), keeps its failure. A case that passed the
first time keeps that pass. This is the runner's default, so
`tests/freecell_suite/run_all.py` does it too.

| Option | Runs |
| --- | --- |
| `--main` | main suite only, no standalone tests (about 35 minutes) |
| `verifyGamePlay verifyDaily` | only the named tests |
| `--prod` | the App Store build (leaves out the dev-build cases) |
| `--no-open` | does not open the report at the end |
| `--no-rerun` | does not rerun failed tests |

Ctrl-C stops the run; the runner still turns the network back on. The
first-launch and Daily tips cases need FreeCell deleted and reinstalled
without opening it; on an install that has been opened they show SKIP.

## Setup

```bash
./scripts/setup.sh
export DEVICE_UDID=00008130-00010D283A31001C
./scripts/wda.sh          # phone UNLOCKED and online; leave running
```

Then run the smoke test or the full regression:

```bash
./.venv/bin/python tests/connect_check.py
DEVICE_UDID=00008130-00010D283A31001C ./.venv/bin/python -u tests/run_all.py
```

`tests/run_all.py` is the regression. It does not need you to say first vs
subsequent launch: `verifyFirstLaunch` walks the policy links only when the
T&C card is on screen, then the runner puts the phone in Airplane Mode and
turns Wi-Fi off so interstitials cannot interrupt the rest. Start WDA while
the phone is still online; do not restart WDA after the suite goes offline.
`SKIP_OFFLINE=1` leaves the network up.

FreeCell is never on screen while the network is up, because an ad it
loads then shows later in the offline run. Going online closes FreeCell
first (Home, then kill) and leaves it closed; going offline kills it once
the radios are off unless they were already known to be off. The runner
goes offline before the first case and online only at the end, after
closing FreeCell. `verifyFirstLaunch` goes online itself only when a
fresh install's Terms card is up (its policy links load web pages).

`verifyRichFeaturesOn` and `verifyRichFeaturesOff` follow GamePlay. ON goes
main menu → Options, scrolls to Rich Features, turns it on only if it is
off, then plays Easy and requires the timer, score, multiplier and the move
counter beside "menu". OFF deals Easy, keeps that frame as the ON reference,
turns Rich Features off through the table's menu → options, and requires
all four gone on the same deal, then turns it back ON the same way and
requires all four back (`log/RichFeaturesCompare.png`). Both switch cases
read the switch state on Options at every step, and table frames are taken
once the deal animation that replays after Options has stopped.

`verifyRankStrip` follows the same steps for Rank Strip: it reads the switch
on the main menu's Options, turns it on only if it is off, and plays Easy.
Then every run checks both directions on the same deal through the table's
menu → options: reads ON → tap → reads OFF → the A…K strip is gone, then
reads OFF → tap → reads ON → the strip is back. Each switch state is
captured on Options (`log/RankStripOption*.png`) and the three tables sit
side by side in `log/RankStripCompare.png`. Table frames are taken once the
deal animation that replays after Options has stopped. The red "Test
Banner" debug button sits over the switch column near the bottom of
Options, so a row is nudged up the page before its switch is tapped.

`verifySoloStats` runs after Relaunch and `verify_qa_victory` is last. Solo
shows only the best score, so any earlier win would outrank the one Solo
Stats checks; it always resets Solo first and requires none/0 (both empty
crops at >= 0.95 on their own rows — anywhere else they match populated
pages too), wins Easy, requires the
victory **current** score to be Solo's best score (the victory "best"
column is this week's ranking, which Reset Solo does not clear), then
resets Solo and requires none/0.

`verifyRelaunch` is in that suite (after Rank Strip, before Solo Stats). It Homes,
kills the FreeCell process, launches again, and passes when the gameplay
screen is back. The runner then taps Back so later cases start from the
menu.

## Capture-first workflow

Every FreeCell asset is cropped from the FreeCell build. Capture the fresh
install and every screen on the target device:

```bash
./.venv/bin/python tests/capture_walkthrough.py
```

Crop the resulting screenshots into `assets/` using semantic names, then run
the screen and QA tests. The QA gesture and code are already configured, but
the exact FreeCell control locations and victory layout must be verified from
the device.

## Obj-C baselines

`baselines/` holds 43 screenshots of the Obj-C build, FreeCell 7.42.5 (279),
on the iPhone 15 Pro Max in portrait, plus a learned motion mask
(`<Name>.volatile.png`) for each animated screen. The Unity port is compared
against them. **Never re-baseline them to a Unity build** — a large diff is
the finding. `baselines/MANIFEST.md` lists how each screen is reached, the
app state it shows and what it masks.

They only need re-shooting if the Obj-C reference itself is lost. Each pass
needs a fresh install, because phase A reads the untouched state:

```bash
DEVICE_UDID=00008130-00010D283A31001C ./.venv/bin/python -u tests/capture_baselines.py --out log/objc_pass2
./.venv/bin/python scripts/update_baselines.py --src log/objc_pass2 --also log/objc_baselines --replace
./.venv/bin/python tests/compare_unity.py --dir log/objc_baselines   # an independent pass
```

The promoted set came from the second pass. The first and a third pass
compare clean against it, except four screens whose app state differed:
promo icons on the picker after a win (`PlayPickerResume`, `AbandonPrompt`),
the Daily calendar caught mid-hop, and Victory's back / menu drawn white
instead of dim.

To compare a Unity build, capture the same screen names into
`log/unity/<build>/` (`<Name>.png`, or `<Name>_1..3.png`). The capture walk
needs its own navigation: `capture_baselines.py` finds its way by Obj-C
templates. Then:

```bash
./.venv/bin/python tests/compare_unity.py --dir log/unity/<build>
./.venv/bin/python scripts/gen_report.py
```

A pixel counts as changed when any colour channel moves more than 32. A
screen fails when the changed share passes its `max_diff`, or one changed
blob passes 2500 px². Measured on these captures, a recoloured or missing
label fails, and so does a label moved 3 px. A 2 px move, or a line of small
body text moved up to 4 px, is boxed in `log/diff/<build>/diff_<Name>.png`
but can pass, because Obj-C's own small animations (the Victory thumbs-up,
the Last Score arrows, the picker spades) leave blobs of that size. Read the
diff images, not just the table.
