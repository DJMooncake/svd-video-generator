@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.11 environment...
    py -3.11 -m venv .venv
    if errorlevel 1 goto failed
)
if not exist ".venv\svd-setup-complete" (
    echo Downloading CUDA PyTorch. This download can take a while...
    ".venv\Scripts\python.exe" bootstrap.py
    if errorlevel 1 goto failed
    echo Installing CUDA PyTorch...
    ".venv\Scripts\python.exe" -m pip install ".downloads\torch-2.1.2+cu121-cp311-cp311-win_amd64.whl"
    if errorlevel 1 goto failed
    echo Installing application dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
    echo complete>".venv\svd-setup-complete"
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
exit /b

:failed
echo Setup failed. Check the message above, then run start.bat again.
pause
exit /b 1
