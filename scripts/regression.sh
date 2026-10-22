#!/usr/bin/env bash
# One command for a FreeCell regression with a live console.
#
#   ./scripts/regression.sh                    # full regression, dev build (~80 min)
#   ./scripts/regression.sh --main             # main suite only (~35 min)
#   ./scripts/regression.sh verifyGamePlay verifyDaily   # just these tests
#   ./scripts/regression.sh --prod             # the App Store build
#   ./scripts/regression.sh --no-open          # do not open the report at the end
#   ./scripts/regression.sh --no-rerun         # do not rerun failed tests
#   ./scripts/regression.sh stop               # from any terminal: stop a run cleanly
#   ./scripts/regression.sh stop --now         # stop at once, network left as it is
#
# Checks the phone, starts WDA (re-signing it when its profile is due),
# keeps the Mac awake, and shows each test and case live with its result
# and time (scripts/present_regression.py). Failed tests run once more and
# the report is rewritten. Phone plugged in, unlocked and online. For the
# first-launch and Daily tips cases, delete FreeCell and reinstall it
# without opening it first; otherwise they show SKIP. Ctrl+C in the run's
# window is the same as stop, and pressing it twice is stop --now.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export DEVICE_UDID="${DEVICE_UDID:-00008130-00010D283A31001C}"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Ctrl+C for a run in another window: SIGINT to the live console and the
# runner. The runner turns the phone's network back on before it exits.
stop_run() {
  local now="$1" console runner starting pid
  console="$(pgrep -if "python[^ ]* .*scripts/present_regression\.py" | tr '\n' ' ' || true)"
  runner="$(pgrep -if "python[^ ]* .*tests/spider_suite/run_all\.py" | tr '\n' ' ' || true)"
  if [[ -z "${console// }${runner// }" ]]; then
    starting=""
    for pid in $(pgrep -f "bash .*scripts/regression\.sh" || true); do
      [[ "$pid" == "$$" ]] || ps -o args= -p "$pid" | grep -q "regression\.sh stop" || starting+="$pid "
    done
    if [[ -n "$starting" ]]; then
      # shellcheck disable=SC2086
      kill $starting 2>/dev/null || true
      echo ">>> stopped the regression before its tests started (WDA is left running)."
    else
      echo ">>> no regression is running."
    fi
    return 0
  fi
  if [[ -n "$now" ]]; then
    # shellcheck disable=SC2086
    [[ -z "${console// }" ]] || kill -INT $console 2>/dev/null || true
    # shellcheck disable=SC2086
    [[ -z "${runner// }" ]] || kill -KILL $runner 2>/dev/null || true
    echo ">>> regression stopped at once. The phone's network was left as it was; if it is"
    echo "    offline, turn Airplane Mode off and Wi-Fi on before the next run."
    return 0
  fi
  echo ">>> stopping the regression; it turns the phone's network back on first (up to ~2 min)..."
  # shellcheck disable=SC2086
  kill -INT $console $runner 2>/dev/null || true
  for _ in $(seq 1 240); do
    if ! pgrep -if "python[^ ]* .*tests/spider_suite/run_all\.py" >/dev/null; then
      echo ">>> regression stopped; its window shows the summary. WDA is still up"
      echo "    (./scripts/wda.sh stop ends it)."
      return 0
    fi
    sleep 1
  done
  echo ">>> still stopping after 4 min; ./scripts/regression.sh stop --now ends it at once." >&2
  return 1
}

if [[ "${1:-}" == "stop" ]]; then
  case "${2:-}" in
    ""|--now) ;;
    *) echo "usage: ./scripts/regression.sh stop [--now]" >&2; exit 2 ;;
  esac
  stop_run "${2:-}"
  exit 0
fi

build="--dev"
scope="--all"
extra=()
for arg in "$@"; do
  case "$arg" in
    --prod) build="" ;;
    --dev) build="--dev" ;;
    --main) scope="" ;;
    --all) scope="--all" ;;
    --no-open|--no-rerun) extra+=("$arg") ;;
    -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $arg (see --help)" >&2; exit 2 ;;
    *) extra+=("$arg"); scope="" ;;
  esac
done

echo ">>> starting the test driver (WDA) on the iPhone..."
./scripts/wda.sh "$DEVICE_UDID"
echo

args=()
[[ -n "$build" ]] && args+=("$build")
[[ -n "$scope" ]] && args+=("$scope")
exec caffeinate -i ./.venv/bin/python -u scripts/present_regression.py \
  ${args[@]+"${args[@]}"} ${extra[@]+"${extra[@]}"}
