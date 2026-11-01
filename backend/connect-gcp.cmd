@echo off
cd /d "%~dp0"
set "CLOUDSDK_CONFIG=%CD%\.gcloud"
if not exist "%CLOUDSDK_CONFIG%" mkdir "%CLOUDSDK_CONFIG%"
echo Opening Google Cloud sign-in. Sign in with an account that can deploy to your project.
call gcloud.cmd auth login --force
if errorlevel 1 (
  echo Google Cloud sign-in failed.
  pause
  exit /b 1
)
echo Active Google account:
call gcloud.cmd auth list --format="table(account,status)"
echo Available projects:
call gcloud.cmd projects list --format="table(projectId,name)"
pause
