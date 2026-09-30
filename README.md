# FreeCell Solitaire Automation

Standalone Objective-C UI automation for FingerArts FreeCell:

- bundle ID: `com.fingerarts.FreeCell`
- QA code: `943010`
- target: a real USB-connected iPhone through WebDriverAgent and Airtest

This repository is intentionally separate from Spider. Spider is retained only
under [`reference/spider/`](reference/spider/) for implementation patterns and
historical comparison. Active FreeCell code must use FreeCell captures and
FreeCell-specific assertions.

## Current status

The signed WDA for this phone lives in [`wda/`](wda/README.md). `scripts/wda.sh`
finds it automatically — do not point `WDA_PRODUCTS` at `/tmp`.

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

## Capture-first workflow

FreeCell assets are not copied from Spider. Capture the fresh install and every
screen on the target device:

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
