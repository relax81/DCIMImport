@echo off
setlocal
cd /d "%~dp0"
echo Installiere Abhaengigkeiten ...
python -m pip install --upgrade -r requirements.txt pyinstaller || goto :err
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [1/2] Einzelne EXE ...
python -m PyInstaller --noconfirm --onefile --windowed --name DCIMImport --collect-submodules dcim_import --add-data "licenses;licenses" --add-data "LICENSE;." --add-data "THIRD_PARTY_LICENSES.md;." DCIMImport.pyw || goto :err

echo.
echo [2/2] ZIP-Version (Ordner, Qt-DLLs austauschbar) ...
python -m PyInstaller --noconfirm --onedir --windowed --name DCIMImport --distpath build\onedir --workpath build\onedir-work --collect-submodules dcim_import DCIMImport.pyw || goto :err
set "Z=build\onedir\DCIMImport"
copy /y LICENSE "%Z%\LICENSE.txt" >nul
copy /y THIRD_PARTY_LICENSES.md "%Z%\" >nul
python tools\collect_licenses.py "%Z%\licenses" || goto :err
powershell -NoProfile -Command "Compress-Archive -Path build\onedir\DCIMImport -DestinationPath dist\DCIMImport-win64.zip -Force" || goto :err

echo.
echo Fertig:
echo   dist\DCIMImport.exe
echo   dist\DCIMImport-win64.zip
pause
exit /b 0
:err
echo FEHLER beim Bauen.
pause
exit /b 1
