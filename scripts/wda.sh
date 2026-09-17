#!/usr/bin/env bash
set -euo pipefail

UDID="${1:-${DEVICE_UDID:-}}"
PORT="${WDA_PORT:-8100}"
PRODUCTS="${WDA_PRODUCTS:-}"

if [[ -z "$UDID" ]]; then
  echo "Set DEVICE_UDID or pass the device UDID." >&2
  exit 2
fi
if [[ -z "$PRODUCTS" ]]; then
  echo "Set WDA_PRODUCTS to the locally signed WDA Build/Products directory." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
XCTESTRUN="$(find "$PRODUCTS" -maxdepth 1 -name 'WebDriverAgentRunner_*.xctestrun' -print -quit)"
IPROXY_BIN="${IPROXY_BIN:-$(command -v iproxy || true)}"

if [[ -z "$XCTESTRUN" || -z "$IPROXY_BIN" ]]; then
  echo "Missing signed .xctestrun or iproxy." >&2
  exit 2
fi

mkdir -p "$ROOT/log/wda-derived"
DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}" \
  xcodebuild -xctestrun "$XCTESTRUN" -destination "id=$UDID" \
  -derivedDataPath "$ROOT/log/wda-derived" \
  -disable-concurrent-destination-testing test-without-building \
  >"$ROOT/log/wda-serve.log" 2>&1 &
WDA_PID=$!

"$IPROXY_BIN" "$PORT:8100" -u "$UDID" >/dev/null 2>&1 &
IPROXY_PID=$!
trap 'kill "$IPROXY_PID" "$WDA_PID" 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$PORT/status" >/dev/null 2>&1; then
    echo "WDA is UP at http://127.0.0.1:$PORT"
    wait "$WDA_PID"
    exit $?
  fi
  if ! kill -0 "$WDA_PID" 2>/dev/null; then
    cat "$ROOT/log/wda-serve.log" >&2
    exit 5
  fi
  sleep 2
done

echo "WDA did not answer within 120 seconds." >&2
cat "$ROOT/log/wda-serve.log" >&2
exit 6
