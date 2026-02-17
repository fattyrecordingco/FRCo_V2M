# First-Time Setup (Windows)

## 1) Open PowerShell in project folder
```powershell
cd "C:\Users\Asus\OneDrive\Documents\Fatty Recording Co\V2M Software"
```

## 2) Run one-time setup
```powershell
.\scripts\setup_first_time.ps1
```

This will:
- create `.venv`
- install dependencies
- run tests

## 3) Start the app
```powershell
.\scripts\start_ui.ps1
```

## 4) Open in browser
Go to:
`http://localhost:8501`

## 5) First usage path
1. `Analyze Audio` page:
   - record from mic or upload a file
   - choose scale mode (`auto` or `manual`)
   - press `Analyze and Build Project`
2. `Project Explorer` page:
   - inspect generated project folders
   - download `melody.mid`, `drums.mid`, `combined.mid`
3. `Producer Assistant` page:
   - get arrangement/layering route suggestions

## Notes
- Generated project artifacts are saved under `projects/`.
- UI-generated quick MIDI ideas are saved under `out/ui/`.
