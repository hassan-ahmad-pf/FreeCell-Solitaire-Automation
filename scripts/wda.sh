#!/usr/bin/env bash
# Start the signed WebDriverAgent committed at wda/. No rebuild, no /tmp.
#
#   ./scripts/wda.sh [UDID]   # start if down, then return (runner stays up)
#   ./scripts/wda.sh stop
#   ./scripts/wda.sh status
#
# Phone UNLOCKED and ONLINE for a start. The runner is detached: this script
# exits once HTTP answers so closing a terminal cannot kill WDA. The suite
# turns Wi-Fi back on when it finishes so the next start can trust the cert.
set -euo pipefail

PORT="${WDA_PORT:-8100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IPROXY_BIN="${IPROXY_BIN:-$(command -v iproxy || true)}"
DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
PIDFILE="${WDA_PIDFILE:-$ROOT/log/wda.pids}"
SERVE_LOG="$ROOT/log/wda-serve.log"
DERIVED_OUT="${WDA_DERIVED_OUT:-$ROOT/log/wda-derived}"

CMD="start"
UDID="${DEVICE_UDID:-}"
for arg in "$@"; do
  case "$arg" in
    start|stop|status) CMD="$arg" ;;
    *) UDID="$arg" ;;
  esac
done

up() {
  curl -fsS -m 2 "http://127.0.0.1:$PORT/status" >/dev/null 2>&1
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
  echo ">>> [wda] stopped."
  exit 0
fi

if [[ -z "$IPROXY_BIN" ]]; then
  echo "Missing iproxy." >&2
  exit 2
fi

if [[ -n "${WDA_PRODUCTS:-}" ]]; then
  PRODUCTS="$WDA_PRODUCTS"
  SOURCE="WDA_PRODUCTS override"
elif ls "$ROOT/wda"/WebDriverAgentRunner_*.xctestrun >/dev/null 2>&1; then
  PRODUCTS="$ROOT/wda"
  SOURCE="in-repo (wda/)"
else
  echo "ERROR: no signed WDA build at $ROOT/wda" >&2
  echo "       Rebuild with SETUP notes, or set WDA_PRODUCTS=/path/to/Build/Products" >&2
  exit 2
fi

if [[ -z "$UDID" ]] && command -v idevice_id >/dev/null 2>&1; then
  UDID="$(idevice_id -l | head -n1)"
fi
if [[ -z "$UDID" ]]; then
  echo "ERROR: no device. Plug in an iPhone or pass the UDID." >&2
  exit 1
fi

XCTESTRUN="$(find "$PRODUCTS" -maxdepth 1 -name 'WebDriverAgentRunner_*.xctestrun' -print -quit)"
if [[ -z "$XCTESTRUN" ]]; then
  echo "ERROR: no WebDriverAgentRunner_*.xctestrun under $PRODUCTS" >&2
  exit 2
fi

echo ">>> [wda] device: $UDID   port: $PORT"
echo ">>> [wda] signed build [$SOURCE]: $XCTESTRUN"

if up; then
  echo "WDA is already UP at http://127.0.0.1:$PORT"
  exit 0
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
  echo "ERROR: xcodebuild exited before WDA came up. Tail of $SERVE_LOG:" >&2
  tail -n 40 "$SERVE_LOG" >&2
  if grep -q "Developer App Certificate is not trusted" "$SERVE_LOG"; then
    echo "" >&2
    echo "WDA cannot start while the phone is in Airplane Mode." >&2
    echo "iOS re-checks the developer cert on the network. Turn Wi-Fi on" >&2
    echo "(or Airplane Mode off), unlock the phone, then run ./scripts/wda.sh." >&2
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
