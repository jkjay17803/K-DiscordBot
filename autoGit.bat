@echo off
chcp 65001
setlocal enabledelayedexpansion

rem === Initialize git repository if not exists ===
if not exist ".git" (
    echo [+] Initializing git repository...
    git init
)

rem === Configure Git user if not set ===
for /f "delims=" %%i in ('git config --get user.name 2^>nul') do set "GIT_USERNAME=%%i"
if "!GIT_USERNAME!"=="" (
    set /p GIT_USERNAME=Enter Git user.name:
    git config --global user.name "!GIT_USERNAME!"
)

for /f "delims=" %%i in ('git config --get user.email 2^>nul') do set "GIT_EMAIL=%%i"
if "!GIT_EMAIL!"=="" (
    set /p GIT_EMAIL=Enter Git user.email:
    git config --global user.email "!GIT_EMAIL!"
)

rem === Ensure .env is ignored and removed from staging ===
if not exist ".gitignore" echo .env > .gitignore
findstr /x ".env" .gitignore >nul 2>&1
if errorlevel 1 echo .env>>.gitignore
git rm --cached .env 2>nul

rem === Check remote repository ===
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    set /p REMOTE_URL=Enter remote URL:
    git remote add origin "!REMOTE_URL!"
    echo [+] Remote 'origin' added.
) else (
    echo [+] Remote 'origin' already exists.
)

rem === Commit & push ===
echo [+] Commit message
set /p message=Commit message:

git branch -M main
git add .

rem Only commit if there are changes
git diff-index --quiet HEAD || git commit -m "!message!"

git push origin main --force
echo [+] Push SUCCESS
pause
