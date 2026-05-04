@echo off
setlocal
set HTTPS_PROXY=http://127.0.0.1:10808
set HTTP_PROXY=http://127.0.0.1:10808
cd /d "%~dp0"
echo [Proxy] http://127.0.0.1:10808
echo [CWD]   %CD%
call claude %*
endlocal
