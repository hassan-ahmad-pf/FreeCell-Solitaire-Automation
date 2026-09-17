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

The FreeCell app is installed on the development phone. The initial screen is a
Terms & Conditions / Privacy Policy card. Before device walkthroughs can run,
WDA must be rebuilt and signed for the phone's UDID. The committed Spider WDA
profile does not include that device.

## Setup

```bash
./scripts/setup.sh
export DEVICE_UDID=00008130-00010D283A31001C
export WDA_PRODUCTS=/tmp/wda-freecell-build/Build/Products
```

If a signed runner is already installed on the phone, attach to it without
reinstalling the repository's incompatible WDA artifact:

```bash
WDA_ATTACH=1 ./scripts/wda.sh "$DEVICE_UDID"
```

For a newly signed local runner, use:

```bash
WDA_PRODUCTS="$WDA_PRODUCTS" ./scripts/wda.sh "$DEVICE_UDID"
```

Then run the smoke test:

```bash
./.venv/bin/python tests/connect_check.py
```

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
