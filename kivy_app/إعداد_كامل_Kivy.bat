@echo off
chcp 65001 >nul
color 0A
title ADR - إعداد كامل لـ Kivy

echo.
echo ═══════════════════════════════════════════════════
echo        🔧 إعداد كامل لـ Kivy/KivyMD
echo ═══════════════════════════════════════════════════
echo.

cd /d "%~dp0"

REM التحقق من Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python غير مثبت!
    echo.
    echo 📥 حمّل Python من: https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo ✅ Python موجود
echo.

echo [1/4] 📦 تثبيت Kivy...
pip install kivy
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل تثبيت Kivy!
    pause
    exit /b 1
)
echo    ✅ تم تثبيت Kivy
echo.

echo [2/4] 📦 تثبيت KivyMD...
pip install kivymd
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل تثبيت KivyMD!
    pause
    exit /b 1
)
echo    ✅ تم تثبيت KivyMD
echo.

echo [3/4] 📦 تثبيت Requests...
pip install requests
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل تثبيت Requests!
    pause
    exit /b 1
)
echo    ✅ تم تثبيت Requests
echo.

echo [4/4] 📦 تثبيت Buildozer (اختياري)...
pip install buildozer
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  فشل تثبيت Buildozer (اختياري)
) else (
    echo    ✅ تم تثبيت Buildozer
)
echo.

echo ═══════════════════════════════════════════════════
echo              ✅ تم الإعداد بنجاح!
echo ═══════════════════════════════════════════════════
echo.
echo 💡 الخطوات التالية:
echo    1. شغّل Flask API: python web_app.py
echo    2. شغّل التطبيق: python kivy_app/main.py
echo.

pause





















