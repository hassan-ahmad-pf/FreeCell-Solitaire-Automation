#!/usr/bin/env bash
# One command for a FreeCell regression with a live console.
#
#   ./scripts/regression.sh                    # full regression, dev build (~80 min)
#   ./scripts/regression.sh --pick             # numbered list: type a module, or full / main
#   ./scripts/regression.sh --main             # main suite only (~35 min)
#   ./scripts/regression.sh verifyGamePlay verifyDaily   # just these tests
#   ./scripts/regression.sh --prod             # the App Store build
#   ./scripts/regression.sh --no-open          # do not open the report at the end
#   ./scripts/regression.sh --no-rerun         # do not rerun failed tests
#   ./scripts/regression.sh stop               # from any terminal: stop a run cleanly
#   ./scripts/regression.sh stop --now         # stop at once, network left as it is
#
# A stopped run writes and opens the report of the cases run so far at once
# (with --now, of the tests finished so far); the rest read "not run".
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
  runner="$(pgrep -if "python[^ ]* .*tests/freecell_suite/run_all\.py" | tr '\n' ' ' || true)"
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
    echo ">>> regression stopped at once; its window writes the report of the tests finished"
    echo "    so far (log/reports/<version>_<build>/). The phone's network was left as it was;"
    echo "    if it is offline, turn Airplane Mode off and Wi-Fi on before the next run."
    return 0
  fi
  echo ">>> stopping the regression: it writes the report of the cases run so far, then turns"
  echo "    the phone's network back on (up to ~2 min)..."
  # shellcheck disable=SC2086
  kill -INT $console $runner 2>/dev/null || true
  for _ in $(seq 1 240); do
    if ! pgrep -if "python[^ ]* .*tests/freecell_suite/run_all\.py" >/dev/null; then
      echo ">>> regression stopped; its window shows the summary, and the report so far is"
      echo "    log/reports/<version>_<build>/ (log/freecell_suite_report.html is the latest)."
      echo "    WDA is still up (./scripts/wda.sh stop ends it)."
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

# Numbered menu: 1 full, 2 main, then every runnable module. Sets picked.
pick_run() {
  if [[ ! -t 0 ]]; then
    echo ">>> --pick needs a terminal so you can type a number." >&2
    echo "    Or name a test: ./scripts/regression.sh verifyAds" >&2
    exit 2
  fi
  local choice token
  echo
  echo "FreeCell tests — type a number and press Enter:"
  echo
  PYTHONPATH="$ROOT" ./.venv/bin/python -u - <<'PY'
import sys
sys.path.insert(0, "tests/freecell_suite")
import catalog

mods = catalog.pickable()
main = [f"{i} {name}" for i, (name, _n, _kind) in enumerate(mods, start=3)
        if name not in catalog.STANDALONE and name not in catalog.PARKED]

print("   1  * Run full regression")
print("   2  * Run main suite only")
line = "      "
for i, item in enumerate(main):
    piece = item if i == len(main) - 1 else item + ", "
    if len(line) + len(piece) > 76 and line.strip():
        print(line.rstrip())
        line = "      " + piece
    else:
        line += piece
if line.strip():
    print(line.rstrip())
print()
for i, (name, n, kind) in enumerate(mods, start=3):
    extra = []
    if kind == "dev":
        extra.append("dev")
    if name in catalog.STANDALONE:
        extra.append("not in main")
    if name in catalog.PARKED:
        extra.append("parked")
    tag = f"  ({', '.join(extra)})" if extra else ""
    cases = "1 case" if n == 1 else f"{n} cases"
    print(f"  {i:2}  {name:<28} {cases}{tag}")
print()
print("   q  cancel")
PY
  echo
  while true; do
    read -r -p "Number: " choice
    case "$choice" in
      q|Q|"") echo ">>> cancelled."; exit 0 ;;
      1) picked="--all"; return 0 ;;
      2) picked="--main"; return 0 ;;
      *)
        token="$(PYTHONPATH="$ROOT" ./.venv/bin/python -u - <<PY
import sys
sys.path.insert(0, "tests/freecell_suite")
import catalog
mods = [name for name, _n, _kind in catalog.pickable()]
try:
    n = int("$choice")
except ValueError:
    sys.exit(1)
i = n - 3
if 0 <= i < len(mods):
    print(mods[i])
else:
    sys.exit(1)
PY
)" && { picked="$token"; return 0; }
        echo "    type 1, 2, a module number, or q"
        ;;
    esac
  done
}

build="--dev"
scope="--all"
extra=()
pick=0
for arg in "$@"; do
  case "$arg" in
    --prod) build="" ;;
    --dev) build="--dev" ;;
    --main) scope="" ;;
    --all) scope="--all" ;;
    --pick|pick) pick=1 ;;
    --no-open|--no-rerun) extra+=("$arg") ;;
    -h|--help) sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $arg (see --help)" >&2; exit 2 ;;
    *) extra+=("$arg"); scope="" ;;
  esac
done

if [[ "$pick" == "1" ]]; then
  picked=""
  pick_run
  case "$picked" in
    --all) scope="--all" ;;
    --main) scope="" ;;
    *) extra+=("$picked"); scope="" ;;
  esac
  echo ">>> running $picked"
  echo
fi

# Before WDA: a re-sign would restart it under a run already going.
busy="$(pgrep -if "python[^ ]* .*(tests/freecell_suite/[A-Za-z_]+|scripts/present_regression)\.py" \
  | tr '\n' ' ' || true)"
if [[ -n "${busy// }" ]]; then
  echo ">>> a FreeCell test is already running on the phone (pid ${busy% }); two runs would" >&2
  echo "    fail each other. Wait for it to finish, or stop it: ./scripts/regression.sh stop" >&2
  exit 1
fi

echo ">>> starting the test driver (WDA) on the iPhone..."
./scripts/wda.sh "$DEVICE_UDID"
echo

args=()
[[ -n "$build" ]] && args+=("$build")
[[ -n "$scope" ]] && args+=("$scope")
exec caffeinate -i ./.venv/bin/python -u scripts/present_regression.py \
  ${args[@]+"${args[@]}"} ${extra[@]+"${extra[@]}"}
