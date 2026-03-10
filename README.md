# VINS (Voice Input Notation System)

VINS is a local-first voice/audio-to-MIDI desktop app with a React/Tauri desktop client and FastAPI backend.

## 1) Download Latest Installer

Use either of these paths:
- In-repo installer folder: `installers/`
- GitHub release assets: https://github.com/fattyrecordingco/FRCo_V2M/releases/latest

Direct in-repo file locations:
- Windows installer: `installers/windows/VINS_0.1.4_x64_en-US.msi`
- macOS installer (Apple Silicon): `installers/macos/VINS_0.1.4_aarch64.dmg`
- macOS app archive: `installers/macos/VINS.app.zip`

Release pages:
- Latest release page: https://github.com/fattyrecordingco/FRCo_V2M/releases/latest
- All releases: https://github.com/fattyrecordingco/FRCo_V2M/releases

Expected assets in each release:
- Windows: `VINS_<version>_x64_en-US.msi`
- macOS: `VINS_<version>_x64.dmg` (or `VINS_<version>_aarch64.dmg`) and `.app.zip`

## 2) Install (Step-By-Step)

### Windows
1. Open the latest release page.
2. Download `VINS_<version>_x64_en-US.msi`.
3. Double-click the MSI and complete setup.
4. Launch `VINS` from Start Menu.

If you previously installed an older build and see duplicate shortcuts/icons:
1. Open `Settings -> Apps -> Installed apps`.
2. Uninstall older `VINS` entries.
3. Install only the newest MSI from `releases/latest`.

### macOS
1. Open the latest release page.
2. Download the `.dmg` (or `.app.zip`).
3. Open DMG and drag `VINS.app` to `Applications`.
4. Open `Applications -> VINS`.

## 3) macOS Security / Gatekeeper

For signed + notarized builds, VINS should open normally.

If macOS blocks first launch:
1. Right-click `VINS.app` in `Applications`, then click `Open`.
2. Click `Open` again in the warning dialog.
3. If still blocked, open `System Settings -> Privacy & Security` and click `Open Anyway` for VINS.

For unsigned test builds only (developer machines):
```bash
xattr -dr com.apple.quarantine /Applications/VINS.app
```

## 4) Use The App (Step-By-Step)

1. Start VINS and allow microphone access.
2. Select your input device.
3. Record or upload voice audio (humming supported).
4. Choose mode: `notes`, `chords`, `drums`, or `auto`.
5. Review detected MIDI and audio previews.
6. Download generated `.mid` files or session ZIP.

Tips for humming:
- Keep mic close and record in a quiet room.
- Hum sustained notes for cleaner pitch confidence.
- Avoid clipping (too loud) and very short bursts.

## 5) Run From Source (Developers)

Prerequisites:
- Python 3.11+
- Node.js 20+
- Rust toolchain (for Tauri desktop)

### Windows
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_first_time.ps1
powershell -ExecutionPolicy Bypass -File scripts/start_ui.ps1
```
Open `http://127.0.0.1:5173`.

### macOS / Linux
```bash
cd backend
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cd ../frontend
npm install
bash scripts/start_ui.sh
```
Open `http://127.0.0.1:5173`.

## 6) Build Installers Locally

### Windows MSI
```powershell
cd frontend
npm install
npx tauri build --bundles msi
```
Output:
- `frontend/src-tauri/target/release/bundle/msi/*.msi`

For an in-place local desktop update on the current machine:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_local_desktop.ps1
```

### macOS App + DMG (build on macOS)
```bash
cd frontend
npm install
npx tauri build --bundles app,dmg
```
Output:
- `frontend/src-tauri/target/release/bundle/macos/*.app`
- `frontend/src-tauri/target/release/bundle/dmg/*.dmg`

## 7) Release Automation

- `.github/workflows/desktop-release.yml` builds Windows + macOS installers on tag pushes (`v*`).
- On tag builds, assets are attached to GitHub Release automatically.
- `scripts/prepare_release_workspace.ps1` and `scripts/prepare_release_workspace.sh` keep only the latest local installer artifacts in `releases/windows` and `releases/macos`.

## 8) Troubleshooting

### No microphone input
- Check OS microphone permission for VINS.
- Verify correct input device in the app.

### Duplicate app icon or two installs
- Remove older app versions from OS app manager.
- Install only the newest release asset.
- Relaunch once (VINS desktop is configured for single running instance).

### Tauri build fails
- Confirm Rust + Node versions.
- Remove stale output: `frontend/src-tauri/target/`
- Reinstall frontend deps: `cd frontend && npm install`

### macOS still warns
- Confirm installer came from the latest release assets.
- If expected to be signed, verify signing/notarization secrets are configured in GitHub Actions.
