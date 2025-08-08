# Wingman (starter)

Local, human-in-the-loop assistant for dating chats via Windows Phone Link (with browser scaffolding ready).

## Quick start
1. Install system tools (optional but recommended):
   - `winget install UB-Mannheim.TesseractOCR`
   - `winget install AutoHotkey.AutoHotkey`
2. Create env:
   - `conda create -n wingman python=3.11 -y`
   - `conda activate wingman`
3. Install Python deps:
   - `pip install -r requirements.txt`
4. Ensure Ollama is running with `gpt-oss:latest` at `http://localhost:11434`.
5. Run:
   - `python -m app.main`

## Buttons
- Detect Displays: detects monitors + DPI and saves to config.
- Read Profile: scrape profile pane (UIA → OCR fallback), save to data/people/<name>/.
- Read Chat: scrape chat window (UIA → OCR fallback), save chat history.
- Generate: propose 3–5 replies using your model.
- Custom + Rerun: apply your custom instruction and regenerate.
- Paste: writes reply.txt and triggers AHK to paste (you press Enter).

## Config
See `config.yaml`. Use UI dropdowns to switch target (Phone Link vs Browser scaffolding) and paste mode.
