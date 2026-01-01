@echo off
chcp 65001 >nul
color 0B
title ADR - تشغيل تطبيق Kivy

echo.
echo ═══════════════════════════════════════════════════
echo        📱 تشغيل تطبيق Kivy/KivyMD
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

REM الانتقال لمجلد التطبيق
if not exist "kivy_app" (
    echo ❌ مجلد التطبيق غير موجود!
    pause
    exit /b 1
)

cd kivy_app

echo [1/2] 📦 التحقق من التبعيات...
pip show kivy >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo    تثبيت التبعيات...
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ فشل تثبيت التبعيات!
        pause
        exit /b 1
    )
) else (
    echo    ✅ التبعيات موجودة
)
echo.

echo [2/2] 🚀 تشغيل التطبيق...
echo.
echo ⚠️  ملاحظة: تأكد من تشغيل Flask API أولاً
echo    (python web_app.py)
echo.

python main.py

pause





















