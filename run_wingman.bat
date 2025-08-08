@echo off
setlocal
REM Activate conda env and run Wingman
IF NOT DEFINED CONDA_PREFIX (
  echo Trying to find conda...
)
call conda activate wingman || (echo Please run: conda create -n wingman python=3.11 && exit /b 1)
python -m pip install -r requirements.txt
python -m app.main
