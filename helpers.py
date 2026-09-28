"""Small WDA/Airtest helpers shared by the FreeCell tests."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from airtest.core.api import connect_device, snapshot, touch

import config


_SESSION_ID: str | None = None
_PIXEL_SCALE: float | None = None


def wda_status() -> dict:
    """Return WDA status or raise a useful connection error."""
    response = requests.get(f"{config.WDA_URL}/status", timeout=5)
    response.raise_for_status()
    return response.json()


def connect() -> None:
    """Attach Airtest to the already-running WDA session."""
    connect_device(config.DEVICE_URI)


def launch_app(force: bool = False, bundle_id: str | None = None,
               settle: float = 2.5, timeout: int = 30) -> str:
    """Launch an app through WDA, never Airtest's iOS start_app.

    Defaults to FreeCell. Pass another bundle (Settings) for radio control.
    """
    response = requests.post(
        f"{config.WDA_URL}/session",
        json={
            "capabilities": {
                "alwaysMatch": {
                    "bundleId": bundle_id or config.BUNDLE_ID,
                    "forceAppLaunch": force,
                    "shouldTerminateApp": False,
                }
            }
        },
        timeout=timeout,
    )
    response.raise_for_status()
    global _SESSION_ID
    _SESSION_ID = response.json()["value"]["sessionId"]
    if settle:
        time.sleep(settle)
    return _SESSION_ID


def tap(point: tuple[int, int], settle: float = 1.0) -> None:
    """Tap a point already in Airtest's screenshot coordinate space."""
    touch(point)
    if settle:
        time.sleep(settle)


def current_session() -> str:
    if not _SESSION_ID:
        raise RuntimeError("launch_app() must run before WDA actions")
    return _SESSION_ID


def pixel_scale() -> float:
    """Screenshot pixels per WDA point (3.0 on the 1290x2796 iPhone 15 Pro Max)."""
    global _PIXEL_SCALE
    if _PIXEL_SCALE is not None:
        return _PIXEL_SCALE
    from PIL import Image

    pixel_width = Image.open(screenshot("_qa_scale_probe")).width
    data = requests.get(
        f"{config.WDA_URL}/session/{current_session()}/window/size",
        timeout=15,
    ).json().get("value")
    if not isinstance(data, dict) or "width" not in data:
        launch_app(force=False, settle=1.0)
        data = requests.get(
            f"{config.WDA_URL}/session/{current_session()}/window/size",
            timeout=15,
        ).json().get("value") or {}
    point_width = data["width"]
    _PIXEL_SCALE = max(pixel_width / float(point_width), 1.0)
    return _PIXEL_SCALE


def _wda_pointer(pixel: tuple[int, int]) -> tuple[int, int]:
    scale = pixel_scale()
    return int(pixel[0] / scale), int(pixel[1] / scale)


def wda_tap(pixel: tuple[int, int], settle: float = 1.0) -> bool:
    """Tap screenshot-pixel coordinates through WDA (divides by pixel_scale)."""
    x, y = _wda_pointer(pixel)
    actions = {
        "actions": [{
            "type": "pointer",
            "id": "freecell-wda-tap",
            "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                {"type": "pointerDown", "button": 0},
                {"type": "pause", "duration": 80},
                {"type": "pointerUp", "button": 0},
            ],
        }]
    }
    response = requests.post(
        f"{config.WDA_URL}/session/{current_session()}/actions",
        data=json.dumps(actions),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    if settle:
        time.sleep(settle)
    return True


def wda_swipe(start: tuple[int, int], end: tuple[int, int],
              duration_ms: int = 400, settle: float = 0.5) -> bool:
    """Swipe in screenshot-pixel space through WDA (divides by pixel_scale)."""
    x1, y1 = _wda_pointer(start)
    x2, y2 = _wda_pointer(end)
    actions = {
        "actions": [{
            "type": "pointer",
            "id": "freecell-wda-swipe",
            "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": x1, "y": y1},
                {"type": "pointerDown", "button": 0},
                {"type": "pause", "duration": 40},
                {"type": "pointerMove", "duration": duration_ms, "x": x2, "y": y2},
                {"type": "pointerUp", "button": 0},
            ],
        }]
    }
    response = requests.post(
        f"{config.WDA_URL}/session/{current_session()}/actions",
        data=json.dumps(actions),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    if settle:
        time.sleep(settle)
    return True


def active_app() -> str:
    """Foreground bundle id, or '' if WDA will not say."""
    paths = []
    try:
        paths.append(f"/session/{current_session()}/wda/activeAppInfo")
    except RuntimeError:
        pass
    paths.append("/wda/activeAppInfo")
    for path in paths:
        try:
            value = requests.get(f"{config.WDA_URL}{path}", timeout=8).json().get("value") or {}
            return value.get("bundleId") or ""
        except Exception:  # noqa: BLE001
            continue
    return ""


def in_app() -> bool:
    return active_app() == config.BUNDLE_ID


def home(settle: float = 2.0) -> bool:
    """Press Home so the app can write state before a kill. True if it left."""
    try:
        requests.post(f"{config.WDA_URL}/wda/homescreen", json={}, timeout=15)
    except Exception:  # noqa: BLE001
        return False
    time.sleep(settle)
    return not in_app()


# XCUIApplicationState: 0 unknown, 1 not running, 2 background, 3 background
# (suspended), 4 foreground.
APP_NOT_RUNNING = 1


def app_state() -> int:
    """FreeCell's XCUIApplicationState, or -1 if WDA will not say."""
    body = {"bundleId": config.BUNDLE_ID}
    paths = []
    try:
        paths.append(f"/session/{current_session()}/wda/apps/state")
    except RuntimeError:
        pass
    paths.append("/wda/apps/state")
    for path in paths:
        try:
            value = requests.post(
                f"{config.WDA_URL}{path}", json=body, timeout=10,
            ).json().get("value")
            return int(value)
        except Exception:  # noqa: BLE001
            continue
    return -1


def terminate() -> None:
    """Kill the FreeCell process. It must not stay resident in the background."""
    try:
        sid = current_session()
    except RuntimeError:
        sid = None
    paths = []
    if sid:
        paths.append(f"/session/{sid}/wda/apps/terminate")
    paths.append("/wda/apps/terminate")
    for path in paths:
        try:
            requests.post(
                f"{config.WDA_URL}{path}",
                json={"bundleId": config.BUNDLE_ID},
                timeout=20,
            )
            break
        except Exception:  # noqa: BLE001
            continue


def kill_app() -> bool:
    """Terminate FreeCell and wait until it is not running (not just backgrounded)."""
    terminate()
    for _ in range(20):
        state = app_state()
        if state == APP_NOT_RUNNING or state == 0:
            return True
        if state == -1 and not in_app():
            time.sleep(0.3)
            terminate()
            return not in_app()
        time.sleep(0.3)
        terminate()
    return app_state() in (APP_NOT_RUNNING, 0)


def alert_text() -> str:
    """Current native alert message, or '' if none (or WDA cannot see it)."""
    try:
        response = requests.get(
            f"{config.WDA_URL}/session/{current_session()}/alert/text",
            timeout=8,
        )
        if response.status_code != 200:
            return ""
        return response.json().get("value") or ""
    except Exception:  # noqa: BLE001
        return ""


def accept_alert() -> bool:
    """Accept a native confirmation if WDA currently exposes one."""
    if not alert_text():
        return False
    accepted = requests.post(
        f"{config.WDA_URL}/session/{current_session()}/alert/accept",
        timeout=8,
    )
    if accepted.status_code != 200:
        return False
    time.sleep(1.5)
    return True


def rapid_tap(point: tuple[int, int], times: int = 10, gap_ms: int = 45) -> bool:
    """Send a hidden-gesture tap burst as one on-device W3C action."""
    x, y = _wda_pointer(point)
    actions = [{"type": "pointerMove", "duration": 0, "x": x, "y": y}]
    for _ in range(times):
        actions.extend((
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 25},
            {"type": "pointerUp", "button": 0},
            {"type": "pause", "duration": gap_ms},
        ))
    response = requests.post(
        f"{config.WDA_URL}/session/{current_session()}/actions",
        data=json.dumps({"actions": [{
            "type": "pointer",
            "id": "freecell-qa",
            "parameters": {"pointerType": "touch"},
            "actions": actions,
        }]}),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    time.sleep(1.5)
    return True


def screenshot(name: str) -> Path:
    """Capture the current device frame into the ignored log directory."""
    config.LOG.mkdir(parents=True, exist_ok=True)
    path = config.LOG / f"{name}.png"
    snapshot(filename=str(path))
    return path


# ── device radios (Airplane Mode / Wi-Fi) ──────────────────────────
# The functional suite must run OFFLINE so interstitials cannot cover a
# transition. WDA stays up over USB; do not restart wda.sh after this.
# Settings publishes a real accessibility tree, unlike FreeCell.
#
# /element/<id>/click does nothing on the Airplane switch — tap the toggle
# from the row rect instead.

SETTINGS_BUNDLE = "com.apple.Preferences"
AIRPLANE_SWITCH = "com.apple.settings.airplaneMode"
WIFI_ROW = "com.apple.settings.wifi"
WIFI_SWITCHES = (
    "Wi-Fi",   # regular hyphen — iOS 27 Settings
    "Wi‑Fi",   # U+2011 non-breaking hyphen — older Settings
)
_SWITCH_INSET = 39
_ROW_TIMEOUT = 15.0


def _wda_post(path: str, body: dict | None = None, timeout: int = 15) -> dict:
    response = requests.post(
        f"{config.WDA_URL}{path}",
        data=json.dumps(body or {}),
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _wda_get(path: str, timeout: int = 15) -> dict:
    response = requests.get(f"{config.WDA_URL}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def _element(sid: str, name: str, timeout: float = 0.0):
    deadline = time.time() + timeout
    while True:
        try:
            payload = _wda_post(
                f"/session/{sid}/element",
                {"using": "name", "value": name},
            )
            element = (payload.get("value") or {}).get("ELEMENT")
            if element:
                return element
        except Exception:  # noqa: BLE001
            pass
        if time.time() >= deadline:
            return None
        time.sleep(0.4)


def _typed_element(sid: str, name: str, kind: str, timeout: float = 0.0):
    deadline = time.time() + timeout
    escaped = name.replace("'", "\\'")
    while True:
        try:
            payload = _wda_post(
                f"/session/{sid}/element",
                {"using": "predicate string",
                 "value": f"name == '{escaped}' AND type == '{kind}'"},
            )
            element = (payload.get("value") or {}).get("ELEMENT")
            if element:
                return element
        except Exception:  # noqa: BLE001
            pass
        if time.time() >= deadline:
            return None
        time.sleep(0.4)


def _attr(sid: str, el: str, attr: str):
    try:
        return _wda_get(f"/session/{sid}/element/{el}/attribute/{attr}").get("value")
    except Exception:  # noqa: BLE001
        return None


def _open_settings() -> str:
    sid = launch_app(bundle_id=SETTINGS_BUNDLE, settle=1.5, timeout=60)
    if _element(sid, AIRPLANE_SWITCH, timeout=6.0) is None:
        try:
            _wda_post(
                f"/session/{sid}/wda/apps/terminate",
                {"bundleId": SETTINGS_BUNDLE},
            )
        except Exception:  # noqa: BLE001
            pass
        sid = launch_app(bundle_id=SETTINGS_BUNDLE, force=True, settle=1.5, timeout=60)
        _element(sid, AIRPLANE_SWITCH, timeout=_ROW_TIMEOUT)
    return sid


def _read_airplane(sid: str):
    el = _element(sid, AIRPLANE_SWITCH, timeout=_ROW_TIMEOUT)
    if el is None:
        return None
    value = _attr(sid, el, "value")
    return None if value is None else str(value) in ("1", "true", "True")


def _read_wifi(sid: str, timeout: float = _ROW_TIMEOUT) -> str:
    el = _element(sid, WIFI_ROW, timeout=timeout)
    label = _attr(sid, el, "label") if el else None
    if not label:
        return ""
    return label.split(",", 1)[1].strip() if "," in label else label.strip()


def _set_wifi(sid: str, want: bool) -> bool:
    row = _element(sid, WIFI_ROW, timeout=_ROW_TIMEOUT)
    label = _attr(sid, row, "label") if row else ""
    state = label.split(",", 1)[1].strip() if label and "," in label else label
    if bool(state and state.lower() != "off") == want:
        return True
    rect = _attr(sid, row, "rect") if row else None
    if not rect:
        return False
    try:
        _wda_post(
            "/session/{}/wda/tap".format(sid),
            {"x": int(rect["x"] + rect["width"] / 2),
             "y": int(rect["y"] + rect["height"] / 2)},
        )
    except Exception:  # noqa: BLE001
        return False
    switch = None
    for name in WIFI_SWITCHES:
        switch = _typed_element(
            sid, name, "XCUIElementTypeSwitch", timeout=4.0)
        if switch:
            break
    rect = _attr(sid, switch, "rect") if switch else None
    if not rect:
        return False
    current = str(_attr(sid, switch, "value")) in ("1", "true", "True")
    if current != want:
        try:
            _wda_post(
                f"/session/{sid}/wda/tap",
                {"x": int(rect["x"] + rect["width"] - _SWITCH_INSET),
                 "y": int(rect["y"] + rect["height"] / 2)},
            )
        except Exception:  # noqa: BLE001
            return False
        time.sleep(2.0)
    return (
        str(_attr(sid, switch, "value")) in ("1", "true", "True")
    ) == want


def _tap_airplane(sid: str, want: bool, settle: float = 4.0,
                  timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        el = _element(sid, AIRPLANE_SWITCH, timeout=_ROW_TIMEOUT)
        if el is None:
            continue
        if (str(_attr(sid, el, "value")) in ("1", "true", "True")) == want:
            return True
        rect = _attr(sid, el, "rect") or {}
        if not rect:
            time.sleep(0.8)
            continue
        x = int(rect["x"] + rect["width"] - _SWITCH_INSET)
        y = int(rect["y"] + rect["height"] / 2)
        try:
            _wda_post(f"/session/{sid}/wda/tap", {"x": x, "y": y})
        except Exception:  # noqa: BLE001
            time.sleep(0.8)
            continue
        time.sleep(settle)
    return _read_airplane(sid) == want


def set_network(online: bool, wait: float = 75.0, restore: bool = True):
    """Take the device online (True) or offline (False). -> (ok, network name).

    Offline is Airplane Mode on + Wi-Fi off. WDA stays up over USB.
    """
    sid = _open_settings()
    time.sleep(1.5)
    try:
        airplane_ok = _tap_airplane(sid, not online)
        wifi_ok = airplane_ok and _set_wifi(sid, online)
        ok = airplane_ok and wifi_ok
        net = ""
        if ok and online:
            if _element(sid, WIFI_ROW) is None:
                sid = _open_settings()
            deadline = time.time() + wait
            while time.time() < deadline:
                net = _read_wifi(sid, timeout=6.0)
                if net and net.lower() not in ("off", "not connected"):
                    break
                time.sleep(2.0)
            if net.lower() in ("off", "not connected"):
                net = ""
        return ok, net
    finally:
        if restore:
            launch_app(force=False)
