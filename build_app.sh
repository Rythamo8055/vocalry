#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

echo "== 1/6 installing Python deps (venv)"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt pyinstaller

if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then
    echo "installing ffmpeg via Homebrew"
    brew install ffmpeg
  elif command -v dnf >/dev/null; then
    sudo dnf install -y ffmpeg
  else
    echo "WARNING: ffmpeg not found — install it manually (needed for the 8D master step)"
  fi
fi

echo "== 2/6 installing Rust + Tauri CLI"
if ! command -v rustc >/dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
  source "$HOME/.cargo/env"
fi
if command -v npm >/dev/null; then
  npm install -g @tauri-apps/cli
  TAURI="tauri"
else
  cargo install tauri-cli --locked
  TAURI="cargo tauri"
fi

echo "== 3/6 building backend binary with PyInstaller"
rm -rf build backend-dist
pyinstaller --noconfirm backend.spec
cp -R dist/8d-backend/_internal backend-dist/_internal
cp dist/8d-backend/8d-backend backend-dist/8d-backend

echo "== 4/6 preparing models + icons"
mkdir -p src-tauri/resources/models
mkdir -p src-tauri/binaries
python3 scripts/gen_icon.py
$TAURI icon src-tauri/icons/icon.png >/dev/null

TRIPLE=""
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) TRIPLE="aarch64-apple-darwin" ;;
  Darwin-x86_64) TRIPLE="x86_64-apple-darwin" ;;
  Linux-x86_64) TRIPLE="x86_64-unknown-linux-gnu" ;;
  Linux-aarch64) TRIPLE="aarch64-unknown-linux-gnu" ;;
  *) echo "unsupported platform"; exit 1 ;;
esac
cp backend-dist/8d-backend "src-tauri/binaries/8d-backend-$TRIPLE"

echo "== 5/6 downloading AI models (one time, ~500 MB)"
mkdir -p src-tauri/resources/models
export MODEL_DIR="$APP_DIR/src-tauri/resources/models"
for m in htdemucs_6s.yaml htdemucs_ft.yaml MDX23C-8KFFT-InstVoc_HQ.ckpt; do
  audio-separator -m "$m" --model_file_dir "$MODEL_DIR" --download_model_only >/dev/null
done

echo "== 6/6 building the app (this takes a while)"
$TAURI build

echo "DONE. App bundle is in src-tauri/target/release/bundle/"
