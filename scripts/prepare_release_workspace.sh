#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Cleaning local cache/build folders..."
rm -rf \
  .pytest_cache \
  .mypy_cache \
  .ruff_cache \
  .venv \
  out \
  frontend/src-tauri/target \
  frontend/design-iterations

echo "Staging latest installer bundles (if present)..."
mkdir -p releases/windows
mkdir -p releases/macos

latest_msi=""
if compgen -G "frontend/src-tauri/target/release/bundle/msi/*.msi" > /dev/null; then
  latest_msi="$(ls -t frontend/src-tauri/target/release/bundle/msi/*.msi | head -n1)"
elif compgen -G "out/release/*.msi" > /dev/null; then
  latest_msi="$(ls -t out/release/*.msi | head -n1)"
fi

if [[ -n "$latest_msi" ]]; then
  rm -f releases/windows/*.msi
  cp -f "$latest_msi" releases/windows/
  echo "Copied $(basename "$latest_msi") -> releases/windows"
else
  echo "No MSI installers found. Build one first: cd frontend && npx tauri build --bundles msi"
fi

latest_dmg=""
latest_macos_zip=""
if compgen -G "frontend/src-tauri/target/release/bundle/dmg/*.dmg" > /dev/null; then
  latest_dmg="$(ls -t frontend/src-tauri/target/release/bundle/dmg/*.dmg | head -n1)"
elif compgen -G "out/release/*.dmg" > /dev/null; then
  latest_dmg="$(ls -t out/release/*.dmg | head -n1)"
fi

if compgen -G "frontend/src-tauri/target/release/bundle/macos-zip/*.zip" > /dev/null; then
  latest_macos_zip="$(ls -t frontend/src-tauri/target/release/bundle/macos-zip/*.zip | head -n1)"
elif compgen -G "out/release/*.zip" > /dev/null; then
  latest_macos_zip="$(ls -t out/release/*.zip | head -n1)"
fi

rm -f releases/macos/*.dmg releases/macos/*.zip

if [[ -n "$latest_dmg" ]]; then
  cp -f "$latest_dmg" releases/macos/
  echo "Copied $(basename "$latest_dmg") -> releases/macos"
else
  echo "No DMG installer found. Build on macOS first: cd frontend && npx tauri build --bundles app,dmg"
fi

if [[ -n "$latest_macos_zip" ]]; then
  cp -f "$latest_macos_zip" releases/macos/
  echo "Copied $(basename "$latest_macos_zip") -> releases/macos"
else
  echo "No macOS app ZIP found. Zip the .app bundle from frontend/src-tauri/target/release/bundle/macos if needed."
fi

echo "Workspace cleanup complete."
