@echo off
chcp 65001 >nul
color 0A
title إعداد Kivy السريع

echo.
echo ═══════════════════════════════════════════════════
echo     🐍 إعداد Kivy السريع 🐍
echo ═══════════════════════════════════════════════════
echo.

echo 📦 الخطوة 1: تثبيت المتطلبات...
echo.
pip install kivy kivymd requests cython
echo.

echo ✅ تم تثبيت المتطلبات!
echo.
echo ═══════════════════════════════════════════════════
echo.
echo 📋 الخطوات التالية:
echo.
echo 1️⃣  شغّل السيرفر:
echo    python web_app.py
echo.
echo 2️⃣  شغّل التطبيق:
echo    python main.py
echo    أو
echo    تشغيل_التطبيق.bat
echo.
echo 3️⃣  حدث API URL في main.py:
echo    - افتح: main.py
echo    - غيّر: self.api_base_url
echo.
echo 4️⃣  للوصول من أي شبكة:
echo    - شغّل: تشغيل_الوصول_من_أي_شبكة.bat
echo    - استخدم رابط Tunnel
echo.
echo ═══════════════════════════════════════════════════
echo.
pause
