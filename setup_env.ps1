# Create conda env, install deps, and system tools
param(
  [string]$EnvName = "wingman"
)

conda create -n $EnvName python=3.11 -y
conda activate $EnvName
pip install -r requirements.txt

# Optional system installs via winget
try { winget install UB-Mannheim.TesseractOCR } catch {}
try { winget install AutoHotkey.AutoHotkey } catch {}
