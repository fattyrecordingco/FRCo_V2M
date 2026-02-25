# VINS (Voice Input Notation System)

VINS is a local-first voice/audio-to-MIDI desktop app.

This repository now focuses on the production app stack:
- `frontend/` React + TypeScript UI (with Tauri desktop shell)
- `backend/` FastAPI + audio-to-MIDI processing engine
- `.github/workflows/` CI + desktop release automation
- `scripts/` setup and run scripts

## 1) Download And Run (End Users)

### Windows (Recommended)
1. Open **GitHub Releases** for this repo.
2. Download the latest `VINS_<version>_x64_en-US.msi`.
3. Run the MSI installer.
4. Launch `VINS` from Start menu or desktop shortcut.

### macOS (Recommended)
1. Open **GitHub Releases** for this repo.
2. Download the latest `.dmg` (or `.app.zip`) from the release assets.
3. Open the DMG and drag `VINS.app` into `Applications`.
4. Launch from `Applications`.

Important for macOS trust/security:
- A clean "no unknown developer" experience requires a **signed + notarized** build.
- This repo includes a GitHub Actions release workflow that signs/notarizes macOS builds when Apple credentials are configured (see section 5).

## 2) Run From Source (Developer)

Prerequisites:
- Python 3.11+
- Node.js 20+
- Rust toolchain (for Tauri desktop)

### Windows
1. Install dependencies:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/setup_first_time.ps1
   ```
2. Start backend + frontend dev UI:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/start_ui.ps1
   ```
3. Open `http://127.0.0.1:5173`.

### macOS / Linux
1. Install backend deps:
   ```bash
   cd backend
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```
2. Install frontend deps:
   ```bash
   cd ../frontend
   npm install
   ```
3. Start backend + frontend:
   ```bash
   bash scripts/start_ui.sh
   ```
4. Open `http://127.0.0.1:5173`.

## 3) Build Installers Locally

### Windows MSI
```powershell
cd frontend
npm install
npx tauri build --bundles msi
```
Output:
- `frontend/src-tauri/target/release/bundle/msi/*.msi`

### macOS App + DMG (on a Mac only)
```bash
cd frontend
npm install
npx tauri build --bundles app,dmg
```
Output:
- `frontend/src-tauri/target/release/bundle/macos/*.app`
- `frontend/src-tauri/target/release/bundle/dmg/*.dmg`

## 4) CI / Release Workflows

- `ci.yml` runs lint/tests/build checks.
- `desktop-release.yml` builds desktop installers for Windows + macOS.

`desktop-release.yml` runs on:
- tag push: `v*` (for example `v0.1.3`)
- manual trigger (`workflow_dispatch`)

On tag builds, it publishes release assets automatically.

## 5) macOS Signed + Notarized Builds (No Gatekeeper Warning)

To ship a macOS build that opens cleanly on another Mac, configure these GitHub repo secrets:

- `APPLE_CERTIFICATE_BASE64`
  - Base64-encoded `Developer ID Application` `.p12` certificate
- `APPLE_CERTIFICATE_PASSWORD`
  - Password used when exporting `.p12`
- `KEYCHAIN_PASSWORD`
  - Temporary CI keychain password
- `APPLE_SIGNING_IDENTITY`
  - Example: `Developer ID Application: Fatty Recording Co (TEAMID)`
- `APPLE_ID`
  - Apple developer account email
- `APPLE_APP_SPECIFIC_PASSWORD`
  - App-specific password for notarization
- `APPLE_TEAM_ID`
  - Apple Developer Team ID

What the workflow does:
1. Imports your Developer ID certificate into a temporary macOS keychain.
2. Builds VINS (`.app` + `.dmg`) with Tauri.
3. Notarizes (when Apple secrets are present).
4. Staples notarization tickets and verifies with `spctl`.
5. Uploads assets to GitHub release.

Without these secrets, mac builds can still be created, but macOS may show security warnings on other machines.

## 6) Repository Cleanup Policy

This repo keeps source + release automation only.
Generated artifacts/caches are ignored, including:
- `.coverage`
- `frontend/*.tsbuildinfo`
- `frontend/design-iterations/`
- `out/`, `dist/`, `coverage/`, `frontend/src-tauri/target/`

If you want a one-command local cleanup:
- Windows: `powershell -ExecutionPolicy Bypass -File scripts/prepare_release_workspace.ps1`
- macOS/Linux: `bash scripts/prepare_release_workspace.sh`

## 7) Troubleshooting

### App opens but no microphone input
- Check OS microphone permissions for VINS.
- Ensure the correct input device is selected in the Input panel.

### Tauri build fails
- Confirm Rust toolchain + Node version are installed.
- Delete stale build output:
  - `frontend/src-tauri/target/`
- Reinstall frontend deps:
  - `cd frontend && npm install`

### macOS still warns on open
- Confirm release asset is from a signed/notarized build.
- Verify the workflow ran with all Apple secrets configured.
