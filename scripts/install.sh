#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
INSTALL_DEV="${INSTALL_DEV:-1}"
INSTALL_WEB="${INSTALL_WEB:-1}"
BUILD_WEB="${BUILD_WEB:-0}"

usage() {
  cat <<'USAGE'
Usage: scripts/install.sh [options]

Options:
  --prod          Install runtime Python dependencies only.
  --no-web        Skip web dependency installation.
  --build-web     Build the production web bundle after installing web deps.
  --venv DIR      Use a custom virtual environment directory.
  -h, --help      Show this help.

Environment:
  PYTHON_BIN      Python executable to use, default: python3
  VENV_DIR        Virtual environment path, default: .venv
  INSTALL_DEV     1 installs .[dev], 0 installs runtime package only
  INSTALL_WEB     1 installs web dependencies, 0 skips them
  BUILD_WEB       1 builds web/dist, 0 skips it
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod)
      INSTALL_DEV=0
      shift
      ;;
    --no-web)
      INSTALL_WEB=0
      BUILD_WEB=0
      shift
      ;;
    --build-web)
      BUILD_WEB=1
      shift
      ;;
    --venv)
      if [[ $# -lt 2 ]]; then
        echo "--venv requires a directory." >&2
        exit 2
      fi
      VENV_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
"$VENV_PYTHON" -m ensurepip --upgrade
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

if [[ "$INSTALL_DEV" == "1" ]]; then
  "$VENV_PYTHON" -m pip install -e ".[dev]"
else
  "$VENV_PYTHON" -m pip install -e .
fi

"$VENV_PYTHON" -m pip install fastapi uvicorn aiofiles pytest-cov

if [[ "$INSTALL_WEB" == "1" ]]; then
  if command -v npm >/dev/null 2>&1; then
    npm --prefix "$ROOT_DIR/web" install
    if [[ "$BUILD_WEB" == "1" ]]; then
      npm --prefix "$ROOT_DIR/web" run build
    fi
  else
    echo "npm is required for web installation; rerun with --no-web to skip." >&2
    exit 1
  fi
fi

cat <<EOF
Install complete.

Activate Python environment:
  source "$VENV_DIR/bin/activate"

Run API server:
  "$VENV_PYTHON" -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
EOF
