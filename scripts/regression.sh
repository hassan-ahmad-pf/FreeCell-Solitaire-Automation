#!/usr/bin/env bash
# One command for a FreeCell regression with a live console.
#
#   ./scripts/regression.sh                    # full regression, dev build (~80 min)
#   ./scripts/regression.sh --main             # main suite only (~35 min)
#   ./scripts/regression.sh verifyGamePlay verifyDaily   # just these tests
#   ./scripts/regression.sh --prod             # the App Store build
#   ./scripts/regression.sh --no-open          # do not open the report at the end
#   ./scripts/regression.sh --no-rerun         # do not rerun failed tests
#
# Checks the phone, starts WDA (re-signing it when its profile is due),
# keeps the Mac awake, and shows each test and case live with its result
# and time (scripts/present_regression.py). Failed tests run once more and
# the report is rewritten. Phone plugged in, unlocked and online. For the
# first-launch and Daily tips cases, delete FreeCell and reinstall it
# without opening it first; otherwise they show SKIP.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export DEVICE_UDID="${DEVICE_UDID:-00008130-00010D283A31001C}"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

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
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
