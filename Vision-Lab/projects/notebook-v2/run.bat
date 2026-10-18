@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   النوتبوك v2 - مركز القيادة الموحد
echo   الواجهة: http://127.0.0.1:8110
echo ============================================
python scripts\start_node.py --port 8110 %*
pause
