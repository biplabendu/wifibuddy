#!/usr/bin/env bash
# Run wifibuddy locally.
#
# Usage:
#   ./run.sh                    # full: venv, install, tests, server
#   ./run.sh --skip-tests       # skip the test suite
#   ./run.sh --skip-install     # skip pip install
#   ./run.sh --skip-venv        # use the system python; don't create/activate .venv
#   ./run.sh --no-server        # do everything but starting uvicorn
#   ./run.sh --port 8765        # bind to a different port (default 8000)
#   ./run.sh --host 0.0.0.0     # bind to a different host (default 127.0.0.1)
#   ./run.sh --no-reload        # disable uvicorn --reload
#
# Flags can be combined, e.g.:
#   ./run.sh --skip-install --skip-tests --port 8765
#
# Database:
#   By default, the local server uses a libsql file-mode database at
#   ./wifibuddy.local.db (created automatically on first run). To run
#   against a real Turso instance, export TURSO_DATABASE_URL and
#   TURSO_AUTH_TOKEN before invoking this script.

set -euo pipefail

cd "$(dirname "$0")"

# Default to a local libsql file db when no Turso URL is set. The app's
# libsql client will create the file on first use.
export TURSO_DATABASE_URL="${TURSO_DATABASE_URL:-file:./wifibuddy.local.db}"
export TURSO_AUTH_TOKEN="${TURSO_AUTH_TOKEN:-}"

SKIP_VENV=0
SKIP_INSTALL=0
SKIP_TESTS=0
NO_SERVER=0
RELOAD=1
HOST="127.0.0.1"
PORT="8000"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-venv)    SKIP_VENV=1; shift ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
    --skip-tests)   SKIP_TESTS=1; shift ;;
    --no-server)    NO_SERVER=1; shift ;;
    --no-reload)    RELOAD=0; shift ;;
    --port)         PORT="$2"; shift 2 ;;
    --host)         HOST="$2"; shift 2 ;;
    -h|--help)      sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Unknown flag: $1" >&2; exit 2 ;;
  esac
done

step() { printf "\n\033[1;36m▶ %s\033[0m\n" "$1"; }

# 1. Virtualenv
if [[ "$SKIP_VENV" -eq 0 ]]; then
  if [[ ! -d .venv ]]; then
    step "Creating virtualenv at .venv"
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

PY="${PY:-python}"
command -v "$PY" >/dev/null || PY="python3"

# 2. Dependencies
if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  step "Installing dependencies"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r requirements.txt
else
  echo "↷ skipping install"
fi

# 3. Tests
if [[ "$SKIP_TESTS" -eq 0 ]]; then
  step "Running test suite"
  "$PY" -m pytest -q
else
  echo "↷ skipping tests"
fi

# 4. Server
if [[ "$NO_SERVER" -eq 1 ]]; then
  echo "↷ skipping server (--no-server)"
  exit 0
fi

step "Starting uvicorn on http://${HOST}:${PORT}"
RELOAD_FLAG=()
[[ "$RELOAD" -eq 1 ]] && RELOAD_FLAG=(--reload)
exec "$PY" -m uvicorn src.main:app --host "$HOST" --port "$PORT" "${RELOAD_FLAG[@]}"
