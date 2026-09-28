#!/usr/bin/env bash
# Start the signed WebDriverAgent committed at wda/. No rebuild, no /tmp.
#
#   ./scripts/wda.sh                 # auto-detect USB device, port 8100
#   ./scripts/wda.sh <UDID>
#   WDA_PORT=8200 ./scripts/wda.sh
#   WDA_PRODUCTS=/other/Products ./scripts/wda.sh
#
# Phone UNLOCKED. Start this while the device is still online so iOS can
# re-trust the developer certificate. Leave it running.
set -euo pipefail

PORT="${WDA_PORT:-8100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IPROXY_BIN="${IPROXY_BIN:-$(command -v iproxy || true)}"
DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"

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

UDID="${1:-${DEVICE_UDID:-}}"
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

if curl -fsS -m 2 "http://127.0.0.1:$PORT/status" >/dev/null 2>&1; then
  echo "WDA is already UP at http://127.0.0.1:$PORT"
  exit 0
fi

DERIVED_OUT="${WDA_DERIVED_OUT:-$ROOT/log/wda-derived}"
SERVE_LOG="$ROOT/log/wda-serve.log"
mkdir -p "$(dirname "$SERVE_LOG")" "$DERIVED_OUT"

WDA_PID=""
IPROXY_PID=""
cleanup() {
  echo ""
  echo ">>> [wda] stopping..."
  [[ -n "${IPROXY_PID:-}" ]] && kill "$IPROXY_PID" 2>/dev/null || true
  [[ -n "${WDA_PID:-}" ]] && kill "$WDA_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo ">>> [wda] stopped."
}
trap cleanup INT TERM EXIT

export DEVELOPER_DIR
echo ">>> [wda] launching (log: $SERVE_LOG)..."
xcodebuild -xctestrun "$XCTESTRUN" -destination "id=$UDID" \
  -derivedDataPath "$DERIVED_OUT" \
  -disable-concurrent-destination-testing test-without-building \
  >"$SERVE_LOG" 2>&1 &
WDA_PID=$!

echo ">>> [wda] forwarding $PORT -> device:8100..."
"$IPROXY_BIN" "$PORT:8100" -u "$UDID" >/dev/null 2>&1 &
IPROXY_PID=$!

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$PORT/status" >/dev/null 2>&1; then
    echo "WDA is UP at http://127.0.0.1:$PORT"
    wait "$WDA_PID"
    exit $?
  fi
  if ! kill -0 "$WDA_PID" 2>/dev/null; then
    echo "ERROR: xcodebuild exited before WDA came up. Tail of $SERVE_LOG:" >&2
    tail -n 40 "$SERVE_LOG" >&2
    exit 5
  fi
  sleep 2
done

echo "ERROR: WDA did not answer within 120 seconds." >&2
tail -n 40 "$SERVE_LOG" >&2
exit 6
