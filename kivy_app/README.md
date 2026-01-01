# 📱 تطبيق Android بـ Kivy/KivyMD

## 🎯 نظرة عامة

تطبيق Android كامل مبني بـ Python باستخدام Kivy و KivyMD.

### ✅ المزايا:
- ✅ **Python فقط** - لا يحتاج JavaScript
- ✅ **واجهة Material Design** جميلة مع KivyMD
- ✅ **سهولة البناء** - أسهل من React Native
- ✅ **استخدام نفس قاعدة البيانات** - SQLite موجودة
- ✅ **استخدام نفس API** - يمكن الاتصال بـ Flask API

---

## 📋 المتطلبات

### **1. تثبيت Python 3.8+**

### **2. تثبيت Kivy و KivyMD:**
```bash
pip install kivy kivymd
```

### **3. تثبيت Buildozer (للبناء):**
```bash
pip install buildozer
```

### **4. تثبيت Cython:**
```bash
pip install cython
```

---

## 🚀 البداية السريعة

### **1. تثبيت التبعيات:**
```bash
cd kivy_app
pip install -r requirements.txt
```

### **2. تشغيل التطبيق (للمطورين):**
```bash
python main.py
```

### **3. بناء APK:**
```bash
buildozer android debug
```

---

## 📁 هيكل المشروع

```
kivy_app/
├── main.py                 # نقطة البداية
├── screens/                # الشاشات
│   ├── login_screen.py
│   ├── home_screen.py
│   ├── jobs_screen.py
│   ├── add_job_screen.py
│   └── job_details_screen.py
├── services/               # الخدمات
│   ├── api_service.py     # الاتصال بـ Flask API
│   └── db_service.py      # الاتصال المباشر بقاعدة البيانات
├── models/                # النماذج
│   └── job_model.py
├── utils/                 # الأدوات المساعدة
│   └── helpers.py
├── buildozer.spec         # إعدادات البناء
└── requirements.txt       # التبعيات
```

---

## 🔧 الإعدادات

### **buildozer.spec:**
- تحديث `package.name`
- تحديث `package.domain`
- إضافة التبعيات المطلوبة

---

## 📱 الميزات

- ✅ تسجيل الدخول
- ✅ عرض قائمة الطلبات
- ✅ إضافة طلب جديد
- ✅ تعديل طلب
- ✅ تحديث حالة الطلب
- ✅ إدارة المدفوعات
- ✅ البحث والفلترة

---

## 🏗️ البناء لـ Android

### **الطريقة 1: Buildozer (موصى به)**
```bash
buildozer android debug
```

### **الطريقة 2: Python-for-Android**
```bash
python -m pythonforandroid.toolchain create --requirements=kivy,kivymd
```

---

## 📚 الموارد

- [Kivy Documentation](https://kivy.org/doc/stable/)
- [KivyMD Documentation](https://kivymd.readthedocs.io/)
- [Buildozer Documentation](https://buildozer.readthedocs.io/)

---

## 💡 نصائح

1. **للاختبار السريع:** استخدم `python main.py`
2. **للبناء:** استخدم `buildozer android debug`
3. **للإنتاج:** استخدم `buildozer android release`

---

## ✅ الخلاصة

Kivy/KivyMD خيار ممتاز لبناء تطبيق Android بـ Python!





















