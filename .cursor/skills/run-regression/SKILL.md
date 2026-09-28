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

If `http://127.0.0.1:8100/status` is down, start the in-repo signed build and
leave it running. Do **not** use `/tmp` or `tidevice wdaproxy`.

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation
export DEVICE_UDID="${DEVICE_UDID:-00008130-00010D283A31001C}"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
# phone UNLOCKED and still online
./scripts/wda.sh "$DEVICE_UDID"
```

`scripts/wda.sh` finds `wda/` by itself. Keep that process alive (background
job). Wait until it prints `WDA is UP`. If xcodebuild says **Developer App
Certificate is not trusted**, the phone is offline — bring Wi-Fi / Airplane
Mode back online, then start `wda.sh` again. Do not restart WDA after the
suite goes offline.

## Then the suite

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation
export DEVICE_UDID="${DEVICE_UDID:-00008130-00010D283A31001C}"
PYTHONPATH="$PWD" /Users/hassan/Automation-FA/Spider-Solitaire-Automation/.venv/bin/python -u tests/run_all.py
```

`verifyFirstLaunch` is first. It walks Terms/Privacy only if the card is up,
then goes offline. Passing cases in this list: menu/pages, Choose Look,
Daily, Play, GamePlay, Relaunch (Home then kill on the table — must come
back on the table), QA victory, Solo Stats. `verifyRelaunch` sits before
the QA cases so the kill cannot hide a panel those later tests re-unlock.
Every later case uses `launch_to_menu()`, which also refuses to start
unless the radios are already off. `verifySubsequentLaunch` stays out.

A subset is allowed:

```bash
PYTHONPATH="$PWD" /Users/hassan/Automation-FA/Spider-Solitaire-Automation/.venv/bin/python -u tests/run_all.py verifyPlay verifyHelp
```

Report the printed PASS/FAIL table. Do not treat a first-launch skip as a failure.
Do not start with `verifySubsequentLaunch` — that case is attach-only and fails if the gates are up.
