---
name: run-freecell-regression
description: >-
  Run the FreeCell functional regression suite. Use when the user says
  run regression, run regression on my build, run the suite, or run_all.
---

# Run FreeCell regression

When the user asks to run regression on the FreeCell build, execute the suite.
Do not ask whether this is a first launch or a subsequent launch.

WDA must already be running **while the phone is still online**. The runner
then takes the device offline (Airplane Mode + Wi-Fi off) so interstitials
cannot cover a case. Do not restart WDA after that.

If xcodebuild fails with **Developer App Certificate is not trusted**, the
phone is offline. Bring Wi-Fi / Airplane Mode back online first (the user
must flip the radios if WDA is down — Settings cannot be tapped without it),
relaunch the signed runner + `iproxy`, then `ensure_offline()` before cases.

```bash
cd /Users/hassan/Automation-FA/FreeCell-Solitaire-Automation
export DEVICE_UDID="${DEVICE_UDID:-00008130-00010D283A31001C}"
PYTHONPATH="$PWD" /Users/hassan/Automation-FA/Spider-Solitaire-Automation/.venv/bin/python -u tests/run_all.py
```

`verifyFirstLaunch` is first. It walks Terms/Privacy only if the card is up,
then goes offline. Every later case uses `launch_to_menu()`, which also
refuses to start unless the radios are already off.

A subset is allowed:

```bash
PYTHONPATH="$PWD" /Users/hassan/Automation-FA/Spider-Solitaire-Automation/.venv/bin/python -u tests/run_all.py verifyPlay verifyHelp
```

Report the printed PASS/FAIL table. Do not treat a first-launch skip as a failure.
Do not start with `verifySubsequentLaunch` — that case is attach-only and fails if the gates are up.
