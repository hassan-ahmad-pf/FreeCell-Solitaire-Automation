"""Small WDA helpers shared by the FreeCell tests.

Matching, screenshots, taps and swipes go through WDA HTTP. Airtest's iOS
driver is not used on the hot path — its recover relaunches XCTest and
kills the runner we started with scripts/wda.sh.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import requests

import config
from caselog import says


_SESSION_ID: str | None = None
_PIXEL_SCALE: float | None = None

LINK_ERRORS = (
    "re-acquire session",
    "no such session",
    "invalid session",
    "session does not exist",
    "closed connection",
    "connection aborted",
    "connection reset",
    "connection refused",
    "failed to establish",
    "max retries exceeded",
)


def is_link_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in LINK_ERRORS)


def wda_status() -> dict:
    """Return WDA status or raise a useful connection error."""
    response = requests.get(f"{config.WDA_URL}/status", timeout=5)
    response.raise_for_status()
    return response.json()


def wait_for_status(timeout: float = 15.0, gap: float = 0.45) -> dict | None:
    """Poll /status. Does not touch iproxy or XCTest — a terminate blinks HTTP."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            return wda_status()
        except Exception:  # noqa: BLE001
            time.sleep(gap)
    return None


def drop_session() -> None:
    """Forget the cached session. Terminate of FreeCell invalidates it."""
    global _SESSION_ID
    _SESSION_ID = None


def restart_iproxy() -> None:
    """Re-forward 8100. Does not relaunch xcodebuild (that needs the network)."""
    port = "8100"
    try:
        listeners = subprocess.check_output(
            ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
            text=True,
        ).split()
    except Exception:  # noqa: BLE001
        listeners = []
    for pid in listeners:
        subprocess.run(["kill", pid], check=False)
    iproxy = shutil.which("iproxy") or "/opt/homebrew/bin/iproxy"
    udid = config.DEVICE_UDID
    cmd = [iproxy, f"{port}:8100"]
    if udid:
        cmd.extend(["-u", udid])
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    time.sleep(0.8)


def ensure_link() -> dict:
    """WDA HTTP must answer. Wait out a blink before touching iproxy.

    Killing FreeCell drops the session and USB mux can reset for a few
    seconds. Restarting iproxy on the first failure races the recovering
    runner and takes the rest of the suite down.
    """
    last: Exception | None = None
    got = wait_for_status(timeout=10.0)
    if got:
        return got
    for _ in range(2):
        restart_iproxy()
        got = wait_for_status(timeout=6.0)
        if got:
            return got
        try:
            return wda_status()
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"WDA HTTP is down after iproxy restart: {last}")


def recover_after_app_kill() -> bool:
    """After terminate, wait for HTTP. Restart iproxy only if it stays down."""
    drop_session()
    if wait_for_status(timeout=15.0):
        return True
    print("  WDA HTTP still down after the kill — restarting iproxy only",
          flush=True)
    restart_iproxy()
    return wait_for_status(timeout=8.0) is not None


def start_wda() -> bool:
    """Start the detached in-repo runner. Phone must be online and unlocked."""
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "wda.sh"
    env = os.environ.copy()
    env.setdefault("DEVELOPER_DIR", "/Applications/Xcode.app/Contents/Developer")
    udid = config.DEVICE_UDID
    if udid:
        env["DEVICE_UDID"] = udid
    cmd = [str(script)]
    if udid:
        cmd.append(udid)
    print("  starting ./scripts/wda.sh (detached)", flush=True)
    result = subprocess.run(cmd, cwd=str(root), env=env, timeout=180)
    return result.returncode == 0 and wait_for_status(timeout=8.0) is not None


def revive_wda() -> bool:
    """If the on-device runner died, start wda.sh. Needs the phone online."""
    if wait_for_status(timeout=3.0):
        return True
    print("  WDA runner is down — restarting it (phone must be online)",
          flush=True)
    return start_wda()


def connect() -> None:
    """Confirm the already-running WDA. Never ask Airtest to launch XCTest."""
    ensure_link()


def ensure_session(settle: float = 0.4) -> str:
    """Reuse the WDA session or mint a new one against the live runner."""
    global _SESSION_ID
    if _SESSION_ID:
        try:
            response = requests.get(
                f"{config.WDA_URL}/session/{_SESSION_ID}",
                timeout=5,
            )
            if response.status_code == 200:
                return _SESSION_ID
        except Exception:  # noqa: BLE001
            pass
        _SESSION_ID = None
    return launch_app(force=False, settle=settle)


def reconnect() -> str:
    """Recover a dropped socket/session without touching XCTest."""
    print("  reconnecting WDA over HTTP (no XCTest relaunch)", flush=True)
    ensure_link()
    return ensure_session(settle=0.8)


def launch_app(force: bool = False, bundle_id: str | None = None,
               settle: float = 2.5, timeout: int = 30) -> str:
    """Launch an app through WDA, never Airtest's iOS start_app.

    Defaults to FreeCell. Pass another bundle (Settings) for radio control.
    """
    ensure_link()
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
    global _SESSION_ID, _IDLE_OFF
    _SESSION_ID = response.json()["value"]["sessionId"]
    _IDLE_OFF = False
    if (bundle_id or config.BUNDLE_ID) == config.BUNDLE_ID:
        idle_waits_off(_SESSION_ID)
    if settle:
        time.sleep(settle)
    return _SESSION_ID


# After a gesture WDA waits for the app to go idle, animations included.
# FreeCell does not always report idle, and XCTest then holds the reply for
# 15-30 s (one swipe in nine on Options). FreeCell sessions turn those waits
# off and pause for a fixed time after each gesture instead, about what WDA
# waited on a normal tap or swipe. A new session puts WDA's waits back, so
# the Settings app keeps them for the radio switches.
IDLE_WAITS = ("waitForIdleTimeout", "animationCoolOffTimeout")
TAP_PAUSE = 1.0
SWIPE_PAUSE = 2.0
_IDLE_OFF = False
_PAUSES = True


def idle_waits_off(sid: str) -> bool:
    """Turn off WDA's waits for the app to idle. True when WDA took it."""
    global _IDLE_OFF
    try:
        response = requests.post(
            f"{config.WDA_URL}/session/{sid}/appium/settings",
            json={"settings": {key: 0 for key in IDLE_WAITS}},
            timeout=10,
        )
        _IDLE_OFF = response.ok
    except requests.RequestException:
        _IDLE_OFF = False
    if not _IDLE_OFF:
        print("  WDA's idle waits could not be turned off; gestures wait for "
              "FreeCell to idle", flush=True)
    return _IDLE_OFF


def gesture_pause(pause: float = TAP_PAUSE) -> None:
    """The pause after a gesture, where WDA no longer waits for the app."""
    if _IDLE_OFF and _PAUSES:
        time.sleep(pause)


@contextmanager
def no_gesture_pause():
    """Taps and swipes return as soon as WDA has played them, for frames
    that must be caught while the app is still animating."""
    global _PAUSES
    if not _IDLE_OFF:
        idle_waits_off(current_session())
    before, _PAUSES = _PAUSES, False
    try:
        yield
    finally:
        _PAUSES = before


def tap(point: tuple[int, int], settle: float = 1.0) -> None:
    """Tap a screenshot-pixel point through WDA."""
    wda_tap(point, settle=settle)


def current_session() -> str:
    return ensure_session(settle=0.3)


def cached_session() -> str | None:
    """The last launch's session id, or None. Never checks or mints one."""
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


# With WDA's idle waits on (Settings, or when they could not be turned off)
# a gesture on FreeCell can take 15-30 s, so gestures get a longer timeout.
GESTURE_TIMEOUT = 60
SLOW_GESTURE = 10.0


def post_gesture(actions: dict, what: str, pause: float) -> requests.Response:
    """Play W3C pointer *actions*, then *pause* where WDA no longer waits."""
    started = time.time()
    response = requests.post(
        f"{config.WDA_URL}/session/{current_session()}/actions",
        data=json.dumps(actions),
        headers={"Content-Type": "application/json"},
        timeout=GESTURE_TIMEOUT,
    )
    took = time.time() - started
    if took > SLOW_GESTURE:
        print(f"  WDA took {took:.0f} s to play the {what}", flush=True)
    if response.ok:
        gesture_pause(pause)
    return response


def wda_tap(pixel: tuple[int, int], settle: float = 1.0) -> bool:
    """Tap screenshot-pixel coordinates through WDA (divides by pixel_scale)."""
    ensure_session()
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
    global _SESSION_ID
    for attempt in range(2):
        response = post_gesture(actions, "tap", TAP_PAUSE)
        # An app switch (an ad opening the App Store) can end the session
        # between the session check and the tap.
        if response.status_code != 404 or attempt:
            break
        _SESSION_ID = None
    response.raise_for_status()
    if settle:
        time.sleep(settle)
    return True


def type_keys(text: str) -> bool:
    """Type into the current first responder through WDA, not Airtest."""
    sid = ensure_session()
    response = requests.post(
        f"{config.WDA_URL}/session/{sid}/wda/keys",
        json={"value": list(text)},
        timeout=15,
    )
    gesture_pause()
    return response.status_code == 200


def wda_swipe(start: tuple[int, int], end: tuple[int, int],
              duration_ms: int = 400, settle: float = 0.5) -> bool:
    """Swipe in screenshot-pixel space through WDA (divides by pixel_scale)."""
    ensure_session()
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
    response = post_gesture(actions, "swipe", SWIPE_PAUSE)
    response.raise_for_status()
    if settle:
        time.sleep(settle)
    return True


def active_app() -> str:
    """Foreground bundle id, or '' if WDA will not say.

    Never mints a session — that would relaunch FreeCell while kill_app
    is asking whether the process is dead.
    """
    paths = ["/wda/activeAppInfo"]
    if _SESSION_ID:
        paths.insert(0, f"/session/{_SESSION_ID}/wda/activeAppInfo")
    for path in paths:
        try:
            value = requests.get(f"{config.WDA_URL}{path}", timeout=8).json().get("value") or {}
            return value.get("bundleId") or ""
        except Exception:  # noqa: BLE001
            continue
    return ""


def in_app() -> bool:
    return active_app() == config.BUNDLE_ID


@says("Press the phone's Home button")
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
    """FreeCell's XCUIApplicationState, or -1 if WDA will not say.

    -1 is unknown, not 'still running'. Prefer an existing Settings
    session. Never mint a FreeCell session here — that relaunches the
    app we just killed. Session-less /wda/apps/state is broken on this WDA.
    """
    body = {"bundleId": config.BUNDLE_ID}
    paths = []
    if _SESSION_ID:
        paths.append(f"/session/{_SESSION_ID}/wda/apps/state")
    paths.append("/wda/apps/state")
    for path in paths:
        try:
            payload = requests.post(
                f"{config.WDA_URL}{path}", json=body, timeout=10,
            ).json()
            value = payload.get("value")
            if isinstance(value, dict):
                value = value.get("state", value.get("value"))
            return int(value)
        except Exception:  # noqa: BLE001
            continue
    return -1


def installed_build() -> tuple[str, str] | None:
    """``(version, build)`` of the installed FreeCell, or None if unreadable."""
    import sys

    cmd = [sys.executable, "-m", "tidevice"]
    if config.DEVICE_UDID:
        cmd += ["--udid", config.DEVICE_UDID]
    try:
        out = subprocess.run(cmd + ["appinfo", "--json", config.BUNDLE_ID],
                             capture_output=True, text=True, timeout=30).stdout
        info = json.loads(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if not isinstance(info, dict) or not info.get("CFBundleIdentifier"):
        return None
    return (str(info.get("CFBundleShortVersionString", "")),
            str(info.get("CFBundleVersion", "")))


def os_version() -> str:
    """The device's iOS version, e.g. "27.0.1". "" if unreadable."""
    try:
        status = wda_status()
        return str(status.get("value", status)["os"]["version"])
    except Exception:  # noqa: BLE001
        return ""


def _device_info(key: str) -> str:
    cmd = ["ideviceinfo", "-k", key]
    if config.DEVICE_UDID:
        cmd[1:1] = ["-u", config.DEVICE_UDID]
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def device_model() -> str:
    """The model IDENTIFIER, e.g. "iPhone16,2" (not the marketing name)."""
    return _device_info("ProductType")


_CLOCK: tuple[float, object] | None = None  # (phone clock − Mac clock in s, phone tz)


def device_now():
    """The phone's own date and time. Its clock and time zone can differ from
    the Mac's (a date set by hand), and FreeCell's Daily follows the phone.
    Falls back to the Mac's clock when the phone cannot be read."""
    import datetime

    global _CLOCK
    if _CLOCK is None:
        try:
            skew = float(_device_info("TimeIntervalSince1970")) - time.time()
        except ValueError:
            return datetime.datetime.now()
        try:
            from zoneinfo import ZoneInfo

            zone = ZoneInfo(_device_info("TimeZone"))
        except Exception:  # noqa: BLE001
            zone = None
        _CLOCK = (skew, zone)
        if abs(skew) > 60:
            print(f"  the phone's clock is {skew / 3600:+.1f} h off the Mac's — "
                  "dates follow the phone", flush=True)
    skew, zone = _CLOCK
    return datetime.datetime.fromtimestamp(time.time() + skew, zone)


@says("Force-quit FreeCell")
def terminate() -> None:
    """Kill the FreeCell process. It must not stay resident in the background."""
    paths = ["/wda/apps/terminate"]
    if _SESSION_ID:
        paths.insert(0, f"/session/{_SESSION_ID}/wda/apps/terminate")
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
    drop_session()


def _attach_settings() -> str | None:
    """Mint a Settings session so we can read FreeCell without launching it.

    This WDA's session-less /wda/apps/state does not work. A FreeCell
    session after terminate would relaunch the game we just killed.
    """
    try:
        return launch_app(
            force=False,
            bundle_id="com.apple.Preferences",
            settle=0.5,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: Settings session failed: {exc}", flush=True)
        return None


@says("Force-quit FreeCell and wait until it has fully stopped")
def kill_app() -> bool:
    """Terminate FreeCell and wait until it is not running (not just backgrounded).

    After terminate, WDA HTTP often blinks. Wait it out, then ask for
    state through Settings — never through a FreeCell session. A
    persistent -1 means WDA will not say, not that the process survived.
    """
    terminate()
    if wait_for_status(timeout=15.0) is None:
        recover_after_app_kill()
    _attach_settings()
    last = -1
    for _ in range(16):
        last = app_state()
        if last in (APP_NOT_RUNNING, 0):
            print(f"  FreeCell process is dead (state {last})")
            drop_session()
            return True
        if last == -1:
            if _SESSION_ID is None:
                _attach_settings()
            time.sleep(0.4)
            continue
        print(f"  FreeCell still running (state {last}) — terminate again")
        terminate()
        wait_for_status(timeout=8.0)
        _attach_settings()
        time.sleep(0.3)
    drop_session()
    if last in (2, 3, 4):
        return False
    print("  FreeCell state unknown after terminate (WDA will not say) "
          "— treating as killed, not as still running")
    return True


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


@says("Accept the system alert", done=True)
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


def alert_buttons() -> list[str]:
    """Button labels of the current native alert, left to right; [] if none."""
    try:
        response = requests.get(
            f"{config.WDA_URL}/session/{current_session()}/wda/alert/buttons",
            timeout=8,
        )
        value = response.json().get("value") if response.ok else None
    except Exception:  # noqa: BLE001
        return []
    return [str(b) for b in value] if isinstance(value, list) else []


@says(lambda name, settle=1.2: f"Tap {name} on the alert", done=True)
def answer_alert(name: str, settle: float = 1.2) -> bool:
    """Press the alert button labelled *name* ("No", "OK", "Show Me"...)."""
    if not alert_text():
        return False
    for verb in ("accept", "dismiss"):
        try:
            response = requests.post(
                f"{config.WDA_URL}/session/{current_session()}/alert/{verb}",
                json={"name": name}, timeout=8,
            )
        except Exception:  # noqa: BLE001
            return False
        if response.ok:
            time.sleep(settle)
            return True
    return False


ATT_TEXT = "track your activity"


@says("Allow on the App Tracking prompt", done=True)
def allow_tracking(sid: str | None = None) -> bool:
    """Press Allow on FreeCell's tracking (ATT) prompt if WDA can read it.

    iOS draws it out of process, and it follows the phone into Settings
    while the radios change, where it swallows every switch tap. Allow,
    not "Ask App Not to Track": the app wants tracking granted before a
    first launch goes through. Pass *sid* when a fresh session would
    launch FreeCell.
    """
    sid = sid or current_session()
    try:
        response = requests.get(
            f"{config.WDA_URL}/session/{sid}/alert/text", timeout=8)
        text = (response.json().get("value") or "") if response.ok else ""
        if not isinstance(text, str) or ATT_TEXT not in text.lower():
            return False
        accepted = requests.post(
            f"{config.WDA_URL}/session/{sid}/alert/accept",
            json={"name": "Allow"},
            timeout=8,
        )
    except Exception:  # noqa: BLE001
        return False
    time.sleep(1.5)
    if accepted.ok:
        print("  answered the tracking prompt: Allow", flush=True)
    return accepted.ok


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
    response = post_gesture({"actions": [{
        "type": "pointer",
        "id": "freecell-qa",
        "parameters": {"pointerType": "touch"},
        "actions": actions,
    }]}, "tap burst", TAP_PAUSE)
    response.raise_for_status()
    time.sleep(1.5)
    return True


def grab_png() -> bytes:
    """Full-screen PNG from WDA. No Airtest session recover."""
    ensure_link()
    for attempt in range(3):
        try:
            response = requests.get(f"{config.WDA_URL}/screenshot", timeout=15)
            if response.status_code != 200:
                sid = ensure_session(settle=0.2)
                response = requests.get(
                    f"{config.WDA_URL}/session/{sid}/screenshot",
                    timeout=15,
                )
            break
        except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError):
            if attempt == 2:
                raise
            time.sleep(0.5)
    response.raise_for_status()
    payload = response.json().get("value")
    if not isinstance(payload, str):
        raise RuntimeError("WDA screenshot returned no image")
    return base64.b64decode(payload)


def screenshot(name: str) -> Path:
    """Capture the current device frame into the ignored log directory."""
    config.LOG.mkdir(parents=True, exist_ok=True)
    path = config.LOG / f"{name}.png"
    path.write_bytes(grab_png())
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
    "wifiSettings.powerToggle",   # iOS 27.2 Settings (label still "Wi-Fi")
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
        allow_tracking(sid)
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
        allow_tracking(sid)
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
