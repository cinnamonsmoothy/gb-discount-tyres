@echo off
cd /d "%~dp0"
if not exist "node_modules\vite\bin\vite.js" (
  echo Installing website dependencies...
  call npm.cmd install
  if errorlevel 1 (
    echo Installation failed. Check that Node.js and npm are installed.
    pause
    exit /b 1
  )
)
echo Opening GB Discount Tyres at http://127.0.0.1:5173/
call npm.cmd run dev -- --open
