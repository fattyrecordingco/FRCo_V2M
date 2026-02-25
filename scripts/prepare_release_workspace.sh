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

echo "Staging latest Windows installer (if present)..."
mkdir -p releases/windows

latest_msi=""
if compgen -G "frontend/src-tauri/target/release/bundle/msi/*.msi" > /dev/null; then
  latest_msi="$(ls -t frontend/src-tauri/target/release/bundle/msi/*.msi | head -n1)"
elif compgen -G "out/release/*.msi" > /dev/null; then
  latest_msi="$(ls -t out/release/*.msi | head -n1)"
fi

if [[ -n "$latest_msi" ]]; then
  cp -f "$latest_msi" releases/windows/
  echo "Copied $(basename "$latest_msi") -> releases/windows"
else
  echo "No MSI installers found. Build one first: cd frontend && npx tauri build --bundles msi"
fi

echo "Workspace cleanup complete."
