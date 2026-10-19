---
name: run-freecell-regression
description: >-
  Run the FreeCell functional regression suite. Use when the user says
  run regression, run regression on my build, run the suite, or run_all.
---

# Run FreeCell regression

When the user asks to run regression on the FreeCell build, execute the suite.
Do not ask whether this is a first launch or a subsequent launch.

## WDA first

If `http://127.0.0.1:8100/status` is down, start the in-repo signed build.
Do **not** use `/tmp` or `tidevice wdaproxy`. `wda.sh` detaches and **exits**
once HTTP answers — do not leave it as a long-lived agent job (that is what
used to kill WDA when the terminal was closed).

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation
export DEVICE_UDID="${DEVICE_UDID:-00008130-00010D283A31001C}"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
# phone UNLOCKED and still online
./scripts/wda.sh "$DEVICE_UDID"
```

`scripts/wda.sh` finds `wda/` by itself, and re-signs WDA into
`log/wda-build` when its 7-day profile (free Apple ID) has under a day left
or the phone refuses it — no manual rebuild. If it says **Developer App
Certificate is not trusted**, the phone is offline or, after a re-sign,
wants the runner trusted again — ask the user to turn Wi-Fi on and tap
Verify App / Trust under Settings → General → VPN & Device Management,
then run `wda.sh` again. If it says the phone is not connected, ask the
user to plug it in and unlock it. The suite restores Wi-Fi in a `finally`
so a finished run does not leave the phone offline, closing FreeCell first.
Never turn Wi-Fi on with FreeCell on screen (an ad loads and fires later
in the offline run); to stop a run early without its online restore, use
`pkill -9`, then go online only after closing FreeCell. Do not restart WDA
after the suite goes offline, and do not run `./scripts/wda.sh stop`
unless the user asked to stop it.

## Then the suite

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation
export DEVICE_UDID="${DEVICE_UDID:-00008130-00010D283A31001C}"
PYTHONPATH="$PWD" ./.venv/bin/python -u tests/run_all.py
```

The runner goes offline before `verifyFirstLaunch`, which is first. Only if
a fresh install's Terms card is up does it close FreeCell, go online, walk
Terms/Privacy, then press Continue / Allow (ATT) and go offline at once,
before waiting for the menu (going offline kills FreeCell; a late ATT is
Allowed over Settings or on the offline relaunch). Order is menu pages (including Daily, no deal), then
Choose Look (restores the default felt), then Play / GamePlay / Rich
Features ON / Rich Features OFF / Rank Strip / Relaunch (each leaves the
table via Back; Rich Features OFF and Rank Strip turn their switch back
ON in a `finally`), then Solo
Stats (always resets Solo first and requires none/0, wins, matches the
victory current score to Solo's best, resets), then QA victory last so its win cannot
outrank the Solo Stats win. A leftover gameplay screen is never a
lost app: tap Back and continue. Matching, shots, taps and swipes go through WDA HTTP so Airtest cannot
relaunch XCTest mid-suite. A dropped socket reconnects over HTTP and the
case is retried once. `verifyRelaunch` Homes then WDA-terminates, then
passes if relaunch lands on the gameplay screen. A kill may blink WDA
HTTP — wait it out and mint a new session, do not restart iproxy on the
first reset, and do not abort later cases. If the runner itself died, go
online, `./scripts/wda.sh`, go offline, continue.
`verifySubsequentLaunch` stays out.

A subset is allowed:

```bash
PYTHONPATH="$PWD" ./.venv/bin/python -u tests/run_all.py verifyPlay verifyHelp
```

With only the App Store (prod) build installed, add `--prod`: it leaves out
`catalog.DEV_BUILD` (QA wins; the report marks those cases "needs dev
build") and any test not written yet. Then build the HTML report with
`./.venv/bin/python scripts/gen_regression_report.py` (writes
`log/freecell_regression.html`).

Report the printed PASS/FAIL table. Do not treat a first-launch skip as a failure.
Do not start with `verifySubsequentLaunch` — that case is attach-only and fails if the gates are up.

`run_all.py` does not compare screenshots. The Obj-C visual reference is
`baselines/` (see the README's "Obj-C baselines"). Never promote a Unity
capture into it; `scripts/update_baselines.py` refuses anything but 7.42.5 (279).
