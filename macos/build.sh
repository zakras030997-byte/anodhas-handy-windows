#!/bin/bash
set -euo pipefail
# Source overlay only: Windows workflows and branch history are unchanged.
: "${RUNTIME_DIR:?Set RUNTIME_DIR to the verified Python/model runtime directory}"
: "${PARAKEET_FILE:?Set PARAKEET_FILE to the Parakeet Q4_K_M GGUF file}"
: "${SDKROOT:?Set SDKROOT to a compatible installed macOS SDK}"
recipe_dir="$(cd "$(dirname "$0")" && pwd)"
job_dir="${BUILD_DIR:-$(mktemp -d -t anodhas-handy-build)}"
upstream_sha=14f6f0d31cb22a4268acfbddba3052820fd0a06e
mkdir -p "$job_dir"
if [ -e "$job_dir/source" ]; then
  echo "Source output exists; choose a fresh BUILD_DIR" >&2
  exit 1
fi
git init "$job_dir/source"
git -C "$job_dir/source" remote add origin https://github.com/cjpais/Handy.git
git -C "$job_dir/source" fetch --depth 1 origin "$upstream_sha"
git -C "$job_dir/source" checkout --detach FETCH_HEAD
git -C "$job_dir/source" apply --check "$recipe_dir/handy-voice.patch"
git -C "$job_dir/source" apply "$recipe_dir/handy-voice.patch"
python3.12 - "$recipe_dir/brand-icon.png" "$job_dir/source" <<'PY'
import sys
from pathlib import Path
from PIL import Image
im=Image.open(sys.argv[1]).convert('RGBA');root=Path(sys.argv[2]);icons=root/'src-tauri/icons'
im.save(icons/'icon.icns',format='ICNS');im.save(icons/'icon.png');im.save(icons/'icon.ico',format='ICO',sizes=[(32,32),(48,48),(128,128),(256,256)])
for name,sz in [('32x32.png',32),('128x128.png',128),('128x128@2x.png',256)]:im.resize((sz,sz),Image.Resampling.LANCZOS).save(icons/name)
im.resize((256,256),Image.Resampling.LANCZOS).save(root/'public/anodhas-icon.png')
PY
(
 cd "$job_dir/source"
 bun install --frozen-lockfile
 CMAKE_POLICY_VERSION_MINIMUM=3.5 bun run tauri build --bundles app
)
python3.12 "$recipe_dir/package_offline.py" --app "$job_dir/source/src-tauri/target/release/bundle/macos/ANODHAS Handy.app" --runtime "$RUNTIME_DIR" --parakeet "$PARAKEET_FILE" --out "$job_dir/stage/ANODHAS Handy.app" --entitlements "$job_dir/source/src-tauri/Entitlements.plist"
ln -s /Applications "$job_dir/stage/Applications"
hdiutil create -volname 'ANODHAS Handy 0.9.9' -srcfolder "$job_dir/stage" -format UDZO -ov "$job_dir/ANODHAS-Handy-0.9.9-macOS-arm64.dmg"
hdiutil verify "$job_dir/ANODHAS-Handy-0.9.9-macOS-arm64.dmg"
