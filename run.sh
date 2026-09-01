#!/usr/bin/env sh
set -eu

case "$0" in
    */*) SCRIPT_DIR=${0%/*} ;;
    *) SCRIPT_DIR=. ;;
esac
SCRIPT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR" && pwd)
cd "$SCRIPT_DIR"

full=false
setup_only=false
for argument in "$@"; do
    case "$argument" in
        --full) full=true ;;
        --setup-only) setup_only=true ;;
        --help)
            echo "Usage: ./run.sh [--full] [--setup-only]"
            echo "  --full        Install the optional Florence-2 dependencies."
            echo "  --setup-only  Install dependencies without starting Streamlit."
            exit 0
            ;;
        *) echo "Unknown option: $argument"; exit 2 ;;
    esac
done

if ! command -v uv >/dev/null 2>&1; then
    echo "[ClaimKit] uv is not installed."
    echo "Install it from https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

set -- sync --locked --python 3.12 --extra app --extra ocr
if [ "$full" = true ]; then
    set -- "$@" --extra vlm
fi

echo "[ClaimKit] Preparing the local environment..."
uv "$@"

if [ "$setup_only" = true ]; then
    echo "[ClaimKit] Setup complete."
    exit 0
fi

echo "[ClaimKit] Opening http://127.0.0.1:8501"
exec uv run streamlit run src/claimkit/app.py
