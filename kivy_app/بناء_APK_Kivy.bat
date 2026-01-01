@echo off
chcp 65001 >nul
color 0A
title ADR - بناء APK بـ Kivy

echo.
echo ═══════════════════════════════════════════════════
echo        📦 بناء APK بـ Kivy/KivyMD
echo ═══════════════════════════════════════════════════
echo.

REM حفظ المجلد الحالي
set "ORIGINAL_DIR=%CD%"

REM البحث عن مجلد kivy_app
set "KIVY_APP_DIR="

REM التحقق من المجلد الحالي
if exist "kivy_app\buildozer.spec" (
    set "KIVY_APP_DIR=%CD%\kivy_app"
    goto :found_kivy_app
)

REM البحث في مجلد الملف نفسه
cd /d "%~dp0"
if exist "buildozer.spec" (
    set "KIVY_APP_DIR=%CD%"
    goto :found_kivy_app
)

REM البحث في المجلد الرئيسي
cd /d "%~dp0\.."
if exist "kivy_app\buildozer.spec" (
    set "KIVY_APP_DIR=%CD%\kivy_app"
    goto :found_kivy_app
)

REM البحث من المجلد الأصلي
cd /d "%ORIGINAL_DIR%"
if exist "kivy_app\buildozer.spec" (
    set "KIVY_APP_DIR=%CD%\kivy_app"
    goto :found_kivy_app
)

REM البحث في المجلدات الأب
set "SEARCH_DIR=%CD%"
:search_parent
cd /d "%SEARCH_DIR%\.."
if exist "kivy_app\buildozer.spec" (
    set "KIVY_APP_DIR=%CD%\kivy_app"
    goto :found_kivy_app
)
if "%CD%"=="%SEARCH_DIR%" goto :not_found
set "SEARCH_DIR=%CD%"
goto :search_parent

:not_found
echo ❌ لم يتم العثور على مجلد kivy_app!
echo.
echo 💡 تأكد من أنك في مجلد المشروع أو قريب منه
echo.
pause
exit /b 1

:found_kivy_app
cd /d "%KIVY_APP_DIR%"
echo ✅ تم العثور على مجلد kivy_app: %KIVY_APP_DIR%
echo.

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

REM التحقق من Buildozer
python -m buildozer --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  Buildozer غير مثبت
    echo.
    echo 📦 تثبيت Buildozer و Cython...
    pip install buildozer cython >nul 2>&1
    REM التحقق مرة أخرى بعد التثبيت
    python -m buildozer --version >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ فشل تثبيت Buildozer!
        echo.
        echo 💡 جرب يدوياً: pip install buildozer cython
        pause
        exit /b 1
    )
    echo    ✅ تم تثبيت Buildozer بنجاح
) else (
    echo ✅ Buildozer موجود
)

REM التحقق من أن Buildozer يعرف android
python -m buildozer android --help >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️  ⚠️  ⚠️  تحذير مهم! ⚠️  ⚠️  ⚠️
    echo.
    echo Buildozer لا يعمل مباشرة على Windows!
    echo يحتاج إلى بيئة Linux (WSL أو Docker).
    echo.
    echo ✅ الحلول المتاحة:
    echo.
    echo [1] استخدام WSL (موصى به):
    echo    1. ثبّت WSL: wsl --install
    echo    2. في WSL: cd /mnt/c/Users/LENOVO/OneDrive/Desktop/adr_maintenance_system/kivy_app
    echo    3. في WSL: buildozer android debug
    echo.
    echo [2] استخدام PWA (الأسهل - لا يحتاج بناء APK):
    echo    - شغّل: python web_app.py
    echo    - شغّل: تشغيل_الوصول_من_أي_شبكة.bat
    echo    - افتح الرابط على الهاتف وأضفه للشاشة الرئيسية
    echo.
    echo [3] استخدام Docker:
    echo    - ثبّت Docker Desktop
    echo    - استخدم صورة kivy/buildozer
    echo.
    echo 📚 للمزيد: حل_مشكلة_Buildozer_على_Windows.md
    echo.
    echo هل تريد المتابعة على أي حال؟ (قد يفشل)
    choice /C YN /M "المتابعة"
    if errorlevel 2 exit /b 1
)

echo.

echo [1/3] 📦 التحقق من التبعيات...
if exist "requirements.txt" (
    echo    ✅ ملف requirements.txt موجود
    echo    ℹ️  سيتم تثبيت التبعيات تلقائياً أثناء البناء
) else (
    echo    ⚠️  ملف requirements.txt غير موجود
    echo    ℹ️  سيتم استخدام التبعيات من buildozer.spec
)
echo.

echo [2/3] 🧹 تنظيف المشروع...
python -m buildozer android clean >nul 2>&1
echo    ✅ تم التنظيف
echo.

echo [3/3] 🔨 بناء APK...
echo    ⏳ قد يستغرق هذا 10-30 دقيقة...
echo    ⚠️  قد تظهر تحذيرات - هذا طبيعي
echo    ℹ️  في المرة الأولى قد يستغرق وقتاً أطول
echo.

REM بناء APK Debug
python -m buildozer android debug

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ فشل بناء APK!
    echo.
    echo 💡 الحلول:
    echo    1. تأكد من تثبيت Git
    echo    2. تأكد من تثبيت Cython
    echo    3. راجع ملفات السجل في .buildozer/
    echo.
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════
echo              ✅ تم بناء APK بنجاح!
echo ═══════════════════════════════════════════════════
echo.

REM البحث عن APK
set APK_PATH=bin\*.apk

if exist "%APK_PATH%" (
    echo 📁 موقع ملف APK:
    dir /b bin\*.apk
    echo.
    echo 📂 المسار الكامل: %KIVY_APP_DIR%\bin\
    echo.
    
    REM فتح مجلد APK
    echo 📂 فتح مجلد APK...
    start "" "%KIVY_APP_DIR%\bin"
    
    echo.
    echo ═══════════════════════════════════════════════════
    echo.
) else (
    echo ❌ لم يتم العثور على ملف APK!
    echo.
    echo 💡 ابحث في: %KIVY_APP_DIR%\bin\
    echo.
)

pause





















