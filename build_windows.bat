@echo off
python -m PyInstaller --noconfirm --clean --onedir --name LiftSaveWithAi --collect-all ultralytics --add-data "criteria.json;." --add-data "models;models" --add-data "website;website" --collect-all lap app.py
if errorlevel 1 exit /b 1
echo Build created in dist\LiftSaveWithAi. Test on the target PC before distribution.
