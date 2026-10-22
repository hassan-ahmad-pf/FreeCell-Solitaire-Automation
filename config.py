"""FreeCell-specific automation configuration.

Values may be overridden for a different device or local WDA port.
"""
from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GAME_NAME = os.environ.get("GAME_NAME", "FreeCell")
BUNDLE_ID = os.environ.get("BUNDLE_ID", "com.fingerarts.FreeCell")
DEVICE_UDID = os.environ.get("DEVICE_UDID", "").strip()
WDA_URL = os.environ.get("WDA_URL", "http://127.0.0.1:8100")
DEVICE_URI = os.environ.get(
    "DEVICE_URI",
    f"iOS:///{WDA_URL}" + (f"/?udid={DEVICE_UDID}" if DEVICE_UDID else ""),
)
ASSETS = Path(os.environ.get("ASSETS", ROOT / "assets"))
LOG = Path(os.environ.get("LOG", ROOT / "log"))
WDA_PRODUCTS = os.environ.get("WDA_PRODUCTS", "").strip()

# The Obj-C reference set. Only a capture of this build may be promoted into
# it — the Unity port is compared against it, never baselined into it.
BASELINES = Path(os.environ.get("BASELINES", ROOT / "baselines"))
OBJC_VERSION = "7.42.5"          # CFBundleShortVersionString
OBJC_BUILD = "279"               # CFBundleVersion; About prints "279 60706F"

QA_CODE = os.environ.get("QA_CODE", "943010")
QA_TAPS = int(os.environ.get("QA_TAPS", "10"))


def validate() -> list[str]:
    """Return configuration problems without touching the device."""
    errors = []
    if not BUNDLE_ID:
        errors.append("BUNDLE_ID is empty")
    if not DEVICE_UDID:
        errors.append("DEVICE_UDID is not set")
    if not ASSETS.exists():
        errors.append(f"asset directory does not exist: {ASSETS}")
    return errors
