#!/usr/bin/env bash
# Start the signed WebDriverAgent, re-signing it first when its profile is
# about to expire. No /tmp.
#
#   ./scripts/wda.sh [UDID]   # start if down, then return (runner stays up)
#   ./scripts/wda.sh renew    # re-sign now, then (re)start
#   ./scripts/wda.sh stop
#   ./scripts/wda.sh status
#
# A free Apple ID's provisioning profiles last 7 days. When the runner's has
# under WDA_RENEW_HOURS left (or the phone refuses it), WDA is rebuilt from
# Appium's WebDriverAgent source and re-signed into log/wda-build; Xcode must
# be signed in to that Apple ID (Settings → Accounts). wda/ is the committed
# build; whichever of the two has more profile time left is started.
#
# Phone connected by USB, UNLOCKED and ONLINE for a start. The runner is
# detached: this script exits once HTTP answers so closing a terminal cannot
# kill WDA. The suite turns Wi-Fi back on when it finishes so the next start
# can trust the cert.
set -euo pipefail

PORT="${WDA_PORT:-8100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IPROXY_BIN="${IPROXY_BIN:-$(command -v iproxy || true)}"
DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
PIDFILE="${WDA_PIDFILE:-$ROOT/log/wda.pids}"
SERVE_LOG="$ROOT/log/wda-serve.log"
DERIVED_OUT="${WDA_DERIVED_OUT:-$ROOT/log/wda-derived}"
WDA_SOURCE="${WDA_SOURCE:-$HOME/.appium/node_modules/appium-xcuitest-driver/node_modules/appium-webdriveragent}"
WDA_TEAM="${WDA_TEAM:-253XD74VB6}"
WDA_BUNDLE="${WDA_BUNDLE:-com.hassanahmad.WebDriverAgentRunner}"
RENEW_HOURS="${WDA_RENEW_HOURS:-24}"
RENEWED="$ROOT/log/wda-build"
RENEW_LOG="$ROOT/log/wda-build.log"

CMD="start"
FORCE_RENEW=""
UDID="${DEVICE_UDID:-}"
for arg in "$@"; do
  case "$arg" in
    start|stop|status) CMD="$arg" ;;
    renew) CMD="start"; FORCE_RENEW=1 ;;
    *) UDID="$arg" ;;
  esac
done

up() {
  curl -fsS -m 2 "http://127.0.0.1:$PORT/status" >/dev/null 2>&1
}

stop_wda() {
  if [[ -f "$PIDFILE" ]]; then
    # shellcheck disable=SC1090
    source "$PIDFILE"
    [[ -n "${WDA_PID:-}" ]] && kill "$WDA_PID" 2>/dev/null || true
    [[ -n "${IPROXY_PID:-}" ]] && kill "$IPROXY_PID" 2>/dev/null || true
    [[ -f "$ROOT/log/wda-watch.pid" ]] && kill "$(tr -d '[:space:]' < "$ROOT/log/wda-watch.pid")" 2>/dev/null || true
    rm -f "$PIDFILE" "$ROOT/log/wda-watch.pid"
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti TCP:"$PORT" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
  fi
}

# Newest WebDriverAgentRunner_*.xctestrun directly under $1 (one per SDK built).
xctestrun_in() {
  ls -t "$1"/WebDriverAgentRunner_*.xctestrun 2>/dev/null | head -n1 || true
}

# Seconds until the runner's provisioning profile under $1 expires; negative
# once it has, or when there is none.
profile_left() {
  local prov="$1/Debug-iphoneos/WebDriverAgentRunner-Runner.app/embedded.mobileprovision"
  local expires
  expires="$(security cms -D -i "$prov" 2>/dev/null | plutil -extract ExpirationDate raw -o - - 2>/dev/null)" \
    || { echo -1; return; }
  echo $(( $(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%SZ" "$expires" +%s) - $(date +%s) ))
}

renew() {
  if [[ ! -d "$WDA_SOURCE/WebDriverAgent.xcodeproj" ]]; then
    echo "ERROR: no WebDriverAgent source at $WDA_SOURCE (set WDA_SOURCE)" >&2
    exit 2
  fi
  echo ">>> [wda] re-signing WDA for team $WDA_TEAM (log: $RENEW_LOG)..."
  if ! "$DEVELOPER_DIR/usr/bin/xcodebuild" -project "$WDA_SOURCE/WebDriverAgent.xcodeproj" \
      -scheme WebDriverAgentRunner -destination "id=$UDID" -derivedDataPath "$RENEWED" \
      -allowProvisioningUpdates DEVELOPMENT_TEAM="$WDA_TEAM" CODE_SIGN_STYLE=Automatic \
      PRODUCT_BUNDLE_IDENTIFIER="$WDA_BUNDLE" build-for-testing >"$RENEW_LOG" 2>&1; then
    echo "ERROR: re-signing WDA failed. From $RENEW_LOG:" >&2
    grep -E "error:|warning: .*(sign|provision)" "$RENEW_LOG" | tail -n 15 >&2 || true
    echo "" >&2
    echo "Is Xcode signed in to the Apple ID of team $WDA_TEAM (Xcode → Settings → Accounts)?" >&2
    exit 6
  fi
  local left
  left="$(profile_left "$RENEWED/Build/Products")"
  echo ">>> [wda] re-signed; the profile is good for $(( left / 3600 )) h"
}

if [[ "$CMD" == "status" ]]; then
  if up; then
    echo "WDA is UP at http://127.0.0.1:$PORT"
    exit 0
  fi
  echo "WDA is DOWN"
  exit 1
fi

if [[ "$CMD" == "stop" ]]; then
  stop_wda
  echo ">>> [wda] stopped."
  exit 0
fi

if [[ -z "$IPROXY_BIN" ]]; then
  echo "Missing iproxy." >&2
  exit 2
fi

if [[ -z "$UDID" ]] && command -v idevice_id >/dev/null 2>&1; then
  UDID="$(idevice_id -l | head -n1)"
fi
if [[ -z "$UDID" ]]; then
  echo "ERROR: no device. Plug in an iPhone or pass the UDID." >&2
  exit 1
fi
if command -v idevice_id >/dev/null 2>&1 && ! idevice_id -l | grep -qx "$UDID"; then
  echo "ERROR: the iPhone $UDID is not connected to this Mac." >&2
  echo "       Plug it in by USB, unlock it, and tap Trust if it asks." >&2
  exit 1
fi

RENEWED_NOW=""
if [[ -n "${WDA_PRODUCTS:-}" ]]; then
  PRODUCTS="$WDA_PRODUCTS"
  SOURCE="WDA_PRODUCTS override"
else
  PRODUCTS=""
  LEFT=-1
  for dir in "$RENEWED/Build/Products" "$ROOT/wda"; do
    [[ -n "$(xctestrun_in "$dir")" ]] || continue
    dir_left="$(profile_left "$dir")"
    if [[ -z "$PRODUCTS" ]] || (( dir_left > LEFT )); then
      PRODUCTS="$dir"
      LEFT="$dir_left"
    fi
  done
  if [[ -n "$FORCE_RENEW" || -z "$PRODUCTS" ]] || (( LEFT < RENEW_HOURS * 3600 )); then
    if [[ -z "$FORCE_RENEW" && -n "$PRODUCTS" ]]; then
      if (( LEFT < 0 )); then
        echo ">>> [wda] the runner's provisioning profile has expired"
      else
        echo ">>> [wda] the runner's provisioning profile expires in $(( LEFT / 3600 )) h"
      fi
    fi
    renew
    RENEWED_NOW=1
    PRODUCTS="$RENEWED/Build/Products"
    LEFT="$(profile_left "$PRODUCTS")"
  fi
  SOURCE="profile good for $(( LEFT / 86400 )) d $(( LEFT % 86400 / 3600 )) h"
fi

XCTESTRUN="$(xctestrun_in "$PRODUCTS")"
if [[ -z "$XCTESTRUN" ]]; then
  echo "ERROR: no WebDriverAgentRunner_*.xctestrun under $PRODUCTS" >&2
  exit 2
fi

echo ">>> [wda] device: $UDID   port: $PORT"
echo ">>> [wda] signed build [$SOURCE]: $XCTESTRUN"

if up; then
  if [[ -z "$RENEWED_NOW" ]]; then
    echo "WDA is already UP at http://127.0.0.1:$PORT"
    exit 0
  fi
  echo ">>> [wda] restarting the running WDA on the re-signed build"
  stop_wda
  sleep 2
fi

# Stale forwarder holding 8100 with no runner behind it.
if command -v lsof >/dev/null 2>&1; then
  lsof -ti TCP:"$PORT" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
fi

mkdir -p "$(dirname "$SERVE_LOG")" "$DERIVED_OUT" "$(dirname "$PIDFILE")"
: >"$SERVE_LOG"

WDA_PID=""
IPROXY_PID=""
fail_start() {
  [[ -n "${IPROXY_PID:-}" ]] && kill "$IPROXY_PID" 2>/dev/null || true
  [[ -n "${WDA_PID:-}" ]] && kill "$WDA_PID" 2>/dev/null || true
  if grep -qE "provisioning profile has expired|integrity could not be verified" "$SERVE_LOG" \
      && [[ -z "${WDA_RENEW_TRIED:-}" && -z "${WDA_PRODUCTS:-}" ]]; then
    echo ">>> [wda] the phone refused the runner's profile — re-signing and starting once more" >&2
    WDA_RENEW_TRIED=1 exec "$0" renew "$UDID"
  fi
  echo "ERROR: xcodebuild exited before WDA came up. Tail of $SERVE_LOG:" >&2
  tail -n 40 "$SERVE_LOG" >&2
  if grep -q "Developer App Certificate is not trusted" "$SERVE_LOG"; then
    echo "" >&2
    echo "iOS has not verified the runner. It checks the developer cert online," >&2
    echo "so turn Wi-Fi on (or Airplane Mode off) and unlock the phone. If it" >&2
    echo "still refuses, open Settings → General → VPN & Device Management →" >&2
    echo "the Apple Development entry and tap Verify App / Trust. Then run" >&2
    echo "./scripts/wda.sh again." >&2
  fi
  exit 5
}

export DEVELOPER_DIR
DAEMON="$ROOT/scripts/wda_daemon.py"
XCODE_PIDFILE="$ROOT/log/wda-xcode.pid"
IPROXY_PIDFILE="$ROOT/log/wda-iproxy.pid"
echo ">>> [wda] launching (new session, log: $SERVE_LOG)..."
XCODEBUILD="${DEVELOPER_DIR}/usr/bin/xcodebuild"
python3 "$DAEMON" "$XCODE_PIDFILE" "$SERVE_LOG" \
  "$XCODEBUILD" -xctestrun "$XCTESTRUN" -destination "id=$UDID" \
  -derivedDataPath "$DERIVED_OUT" \
  -disable-concurrent-destination-testing test-without-building
WDA_PID="$(tr -d '[:space:]' < "$XCODE_PIDFILE")"

echo ">>> [wda] forwarding $PORT -> device:8100..."
python3 "$DAEMON" "$IPROXY_PIDFILE" "-" \
  "$IPROXY_BIN" "$PORT:8100" -u "$UDID"
IPROXY_PID="$(tr -d '[:space:]' < "$IPROXY_PIDFILE")"

cat >"$PIDFILE" <<EOF
WDA_PID=$WDA_PID
IPROXY_PID=$IPROXY_PID
PORT=$PORT
UDID=$UDID
EOF

for _ in $(seq 1 60); do
  if up; then
    echo "WDA is UP at http://127.0.0.1:$PORT"
    python3 "$DAEMON" "$ROOT/log/wda-watch.pid" "-" \
      python3 "$ROOT/scripts/wda_watch.py" || true
    echo ">>> [wda] runner stays up after this script exits (stop with ./scripts/wda.sh stop)"
    exit 0
  fi
  if ! kill -0 "$WDA_PID" 2>/dev/null; then
    fail_start
  fi
  sleep 2
done

fail_start
