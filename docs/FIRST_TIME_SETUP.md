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
$env:OPENAI_API_KEY="your_openai_api_key"
.\scripts\start_ui.ps1
```

## 4) Open in browser
Go to:
`http://localhost:8501`

## 5) First usage path
1. In chat input, upload/record audio and send:
   - `Analyze this and build a project pack`
2. Ask follow-ups:
   - `suggest chord progression options`
   - `give me arrangement and layering plan`
3. Download generated MIDI directly from assistant responses.

## Notes
- Generated project artifacts are saved under `projects/`.
- UI-generated quick MIDI ideas are saved under `out/ui/`.
