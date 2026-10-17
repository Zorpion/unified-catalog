@echo off
TITLE Unified Data Catalog
cd /d %~dp0

echo ========================================================
echo Starting Unified Data Catalog - Local First
echo ========================================================

:: Forces the script to use the local portable Python folder only
python-embed\python.exe -m streamlit run app.py

pause