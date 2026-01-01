#!/bin/bash

# سكريبت بناء APK عبر WSL
# استخدم هذا السكريبت في WSL (Ubuntu)

echo "========================================"
echo "   ADR - بناء APK بـ Kivy/KivyMD"
echo "   عبر WSL (Windows Subsystem for Linux)"
echo "========================================"
echo ""

# التحقق من WSL
if [ -z "$WSL_DISTRO_NAME" ]; then
    echo "⚠️  تحذير: يبدو أنك لست في WSL"
    echo "   هذا السكريبت مصمم للعمل في WSL"
    echo ""
    read -p "هل تريد المتابعة على أي حال؟ (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# التحقق من Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 غير مثبت!"
    echo ""
    echo "📦 تثبيت Python3..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
    if [ $? -ne 0 ]; then
        echo "❌ فشل تثبيت Python3!"
        exit 1
    fi
fi

echo "✅ Python3 موجود"
echo ""

# التحقق من Buildozer
if ! command -v buildozer &> /dev/null; then
    echo "⚠️  Buildozer غير مثبت"
    echo ""
    echo "📦 تثبيت Buildozer و Cython..."
    pip3 install buildozer cython
    if [ $? -ne 0 ]; then
        echo "❌ فشل تثبيت Buildozer!"
        exit 1
    fi
    echo "✅ تم تثبيت Buildozer بنجاح"
else
    echo "✅ Buildozer موجود"
fi

echo ""

# التحقق من buildozer.spec
if [ ! -f "buildozer.spec" ]; then
    echo "❌ ملف buildozer.spec غير موجود!"
    echo ""
    echo "💡 تأكد من أنك في مجلد kivy_app"
    exit 1
fi

echo "✅ ملف buildozer.spec موجود"
echo ""

# التحقق من main.py
if [ ! -f "main.py" ]; then
    echo "❌ ملف main.py غير موجود!"
    exit 1
fi

echo "✅ ملف main.py موجود"
echo ""

# التحقق من API URL
echo "⚠️  تذكير: تأكد من تحديث API URL في main.py"
echo "   ابحث عن: self.api_base_url"
echo ""
read -p "هل قمت بتحديث API URL؟ (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "💡 افتح main.py وحدث API URL:"
    echo "   nano main.py"
    echo ""
    read -p "اضغط Enter للمتابعة بعد التحديث..."
fi

echo ""
echo "[1/3] 📦 التحقق من التبعيات..."
if [ -f "requirements.txt" ]; then
    echo "   ✅ ملف requirements.txt موجود"
    echo "   ℹ️  سيتم تثبيت التبعيات تلقائياً أثناء البناء"
else
    echo "   ⚠️  ملف requirements.txt غير موجود"
    echo "   ℹ️  سيتم استخدام التبعيات من buildozer.spec"
fi
echo ""

echo "[2/3] 🧹 تنظيف المشروع..."
buildozer android clean > /dev/null 2>&1
echo "   ✅ تم التنظيف"
echo ""

echo "[3/3] 🔨 بناء APK..."
echo "   ⏳ قد يستغرق هذا 20-40 دقيقة..."
echo "   ⚠️  قد تظهر تحذيرات - هذا طبيعي"
echo "   ℹ️  في المرة الأولى قد يستغرق وقتاً أطول"
echo ""

# بناء APK Debug
buildozer android debug

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "   ✅ تم بناء APK بنجاح!"
    echo "========================================"
    echo ""
    
    # البحث عن APK
    if ls bin/*.apk 1> /dev/null 2>&1; then
        echo "📁 موقع ملف APK:"
        ls -lh bin/*.apk
        echo ""
        echo "📂 المسار الكامل:"
        echo "   $(pwd)/bin/"
        echo ""
        
        # نسخ APK إلى Desktop (اختياري)
        read -p "هل تريد نسخ APK إلى Desktop؟ (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp bin/*.apk /mnt/c/Users/LENOVO/Desktop/ 2>/dev/null
            if [ $? -eq 0 ]; then
                echo "✅ تم نسخ APK إلى Desktop"
            else
                echo "⚠️  لم يتم نسخ APK (تحقق من المسار)"
            fi
        fi
    else
        echo "❌ لم يتم العثور على ملف APK!"
        echo ""
        echo "💡 ابحث في: bin/"
    fi
else
    echo ""
    echo "❌ فشل بناء APK!"
    echo ""
    echo "💡 الحلول:"
    echo "   1. راجع ملفات السجل في .buildozer/"
    echo "   2. تأكد من تثبيت جميع التبعيات"
    echo "   3. جرب: buildozer android clean"
    echo ""
    exit 1
fi

echo ""
echo "========================================"
echo ""















