@echo off
cd /d "%~dp0"
python -c "import PySide6, PIL, send2trash" 2>nul || python -m pip install -r requirements.txt
start "" pythonw DCIMImport.pyw
