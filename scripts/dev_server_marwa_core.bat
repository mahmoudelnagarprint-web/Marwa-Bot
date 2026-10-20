@echo off
cd /d "G:\Marwa-Bot\tsmym-wajht-marwa-core"
netstat -ano | findstr ":3000 " | findstr "LISTENING" >nul
if %errorlevel% == 0 ( echo marwa-core dev server already running & exit /b 0 )
"C:\Users\mahmo\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe" "C:\Users\mahmo\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\pnpm\bin\pnpm.mjs" run dev
