#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_NAME="${PACKAGE_NAME:-multi-agent-orchestration}"
VERSION="${VERSION:-$(date +%Y%m%d%H%M%S)}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/dist/packages}"
WORK_DIR="${WORK_DIR:-$ROOT_DIR/build/package}"
INSTALL_DEPS="${INSTALL_DEPS:-1}"
SKIP_WEB_BUILD="${SKIP_WEB_BUILD:-0}"

usage() {
  cat <<'USAGE'
Usage: scripts/package.sh [options]

Options:
  --version VERSION       Package version label, default: timestamp.
  --output-dir DIR        Directory for package artifacts, default: dist/packages.
  --work-dir DIR          Temporary package assembly directory, default: build/package.
  --skip-install          Do not run scripts/install.sh before packaging.
  --skip-web-build        Do not build web/dist before packaging.
  -h, --help              Show this help.

Environment:
  PACKAGE_NAME            Archive base name, default: multi-agent-orchestration
  VERSION                 Package version label
  OUTPUT_DIR              Artifact output directory
  WORK_DIR                Package assembly directory
  INSTALL_DEPS            1 runs install script, 0 skips it
  SKIP_WEB_BUILD          1 skips web build, 0 builds web/dist
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      if [[ $# -lt 2 ]]; then
        echo "--version requires a value." >&2
        exit 2
      fi
      VERSION="$2"
      shift 2
      ;;
    --output-dir)
      if [[ $# -lt 2 ]]; then
        echo "--output-dir requires a directory." >&2
        exit 2
      fi
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --work-dir)
      if [[ $# -lt 2 ]]; then
        echo "--work-dir requires a directory." >&2
        exit 2
      fi
      WORK_DIR="$2"
      shift 2
      ;;
    --skip-install)
      INSTALL_DEPS=0
      shift
      ;;
    --skip-web-build)
      SKIP_WEB_BUILD=1
      shift
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

if [[ ! "$PACKAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "PACKAGE_NAME may only contain letters, numbers, dot, underscore, and dash." >&2
  exit 2
fi

if [[ ! "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "VERSION may only contain letters, numbers, dot, underscore, and dash." >&2
  exit 2
fi

if [[ -z "$WORK_DIR" || "$WORK_DIR" == "/" ]]; then
  echo "WORK_DIR must not be empty or /." >&2
  exit 2
fi

if [[ "$WORK_DIR" == "$ROOT_DIR" ]]; then
  echo "WORK_DIR must not be the repository root." >&2
  exit 2
fi

if [[ "$OUTPUT_DIR" == "$ROOT_DIR" ]]; then
  echo "OUTPUT_DIR must not be the repository root." >&2
  exit 2
fi

if [[ "$INSTALL_DEPS" == "1" ]]; then
  if [[ "$SKIP_WEB_BUILD" == "1" ]]; then
    "$ROOT_DIR/scripts/install.sh" --prod
  else
    "$ROOT_DIR/scripts/install.sh" --prod --build-web
  fi
elif [[ "$SKIP_WEB_BUILD" != "1" ]]; then
  npm --prefix "$ROOT_DIR/web" install
  npm --prefix "$ROOT_DIR/web" run build
fi

PACKAGE_DIR="$WORK_DIR/$PACKAGE_NAME-$VERSION"
ARCHIVE="$OUTPUT_DIR/$PACKAGE_NAME-$VERSION.tar.gz"
CHECKSUM="$ARCHIVE.sha256"

rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR" "$OUTPUT_DIR"

rsync -a \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.ruff_cache/' \
  --exclude 'build/' \
  --exclude 'dist/' \
  --exclude 'web/node_modules/' \
  --exclude 'tests/ui/screenshots/' \
  --exclude 'checkpoints/' \
  --exclude 'logs/' \
  --exclude 'memory/' \
  --exclude 'demo_project/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '.pipeline_thread_*.txt' \
  "$ROOT_DIR/" "$PACKAGE_DIR/"

cat > "$PACKAGE_DIR/INSTALL.md" <<EOF
# Install $PACKAGE_NAME $VERSION

## Local install

\`\`\`bash
scripts/install.sh --prod --build-web
source .venv/bin/activate
python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
\`\`\`

## Development install

\`\`\`bash
scripts/install.sh
source .venv/bin/activate
\`\`\`

## Required runtime configuration

Set one of these before running real model-backed workflows:

\`\`\`bash
export DASHSCOPE_API_KEY="your-key"
# or
export ANTHROPIC_API_KEY="your-key"
\`\`\`
EOF

tar -C "$WORK_DIR" -czf "$ARCHIVE" "$PACKAGE_NAME-$VERSION"
shasum -a 256 "$ARCHIVE" > "$CHECKSUM"

cat <<EOF
Package created:
  $ARCHIVE
  $CHECKSUM

Install from package:
  tar -xzf "$ARCHIVE"
  cd "$PACKAGE_NAME-$VERSION"
  scripts/install.sh --prod --build-web
EOF
