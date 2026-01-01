# 🔄 تحديث API URL في Kivy للوصول من أي شبكة

## 🎯 الهدف

تحديث رابط API في تطبيق Kivy للوصول من أي شبكة في العالم.

---

## 📋 الخطوات

### **الخطوة 1: الحصول على رابط Tunnel**

1. شغّل Tunnel:
   ```bash
   # من المجلد الرئيسي
   تشغيل_الوصول_من_أي_شبكة.bat
   # اختر رقم 1 (Cloudflare Tunnel)
   ```

2. انسخ الرابط:
   ```
   https://abc123-def456.trycloudflare.com
   ```

---

### **الخطوة 2: تحديث API URL**

**الملف:** `kivy_app/main.py`

**البحث عن:**
```python
self.api_base_url = "http://localhost:5000/api"
```

**استبدله بـ:**
```python
self.api_base_url = "https://abc123-def456.trycloudflare.com/api"
```

**مثال كامل:**
```python
class MaintenanceApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"
        self.current_user = None
        # الرابط الجديد
        self.api_base_url = "https://abc123-def456.trycloudflare.com/api"
```

---

### **الخطوة 3: تحديث APIService (اختياري)**

**الملف:** `kivy_app/services/api_service.py`

**البحث عن:**
```python
def __init__(self, base_url: str = "http://localhost:5000/api"):
```

**استبدله بـ:**
```python
def __init__(self, base_url: str = "https://abc123-def456.trycloudflare.com/api"):
```

---

### **الخطوة 4: اختبار**

1. شغّل التطبيق:
   ```bash
   python main.py
   ```

2. اختبر الاتصال:
   - سجّل الدخول
   - جلب الطلبات
   - إضافة طلب جديد

---

## 🔧 إعداد رابط ديناميكي (متقدم)

إذا كنت تريد تغيير الرابط من داخل التطبيق:

### **1. تحديث Settings Screen**

**الملف:** `kivy_app/screens/settings_screen.py`

```python
from kivy.storage.jsonstore import JsonStore
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton

class SettingsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = JsonStore('settings.json')
        
        # حقل إدخال الرابط
        self.url_field = MDTextField(
            hint_text="رابط السيرفر",
            text=self.load_server_url()
        )
        self.add_widget(self.url_field)
        
        # زر الحفظ
        save_btn = MDRaisedButton(
            text="حفظ",
            on_release=self.save_url
        )
        self.add_widget(save_btn)
    
    def load_server_url(self):
        """تحميل الرابط المحفوظ"""
        try:
            if 'server_url' in self.store:
                return self.store.get('server_url')['value']
        except:
            pass
        return "https://abc123-def456.trycloudflare.com"
    
    def save_url(self, instance):
        """حفظ الرابط"""
        url = self.url_field.text
        if not url.startswith('http'):
            url = f"https://{url}"
        
        self.store.put('server_url', value=url)
        
        # تحديث API URL في التطبيق
        app = MDApp.get_running_app()
        if not url.endswith('/api'):
            if url.endswith('/'):
                app.api_base_url = f"{url}api"
            else:
                app.api_base_url = f"{url}/api"
        else:
            app.api_base_url = url
        
        print(f"تم حفظ الرابط: {app.api_base_url}")
```

### **2. تحديث main.py لتحميل الرابط**

**الملف:** `kivy_app/main.py`

```python
def on_start(self):
    """عند بدء التطبيق"""
    try:
        from kivy.storage.jsonstore import JsonStore
        store = JsonStore('settings.json')
        if 'server_url' in store:
            server_url = store.get('server_url')['value']
            if not server_url.endswith('/api'):
                if server_url.endswith('/'):
                    self.api_base_url = f"{server_url}api"
                else:
                    self.api_base_url = f"{server_url}/api"
            else:
                self.api_base_url = server_url
            print(f"تم تحميل الرابط: {self.api_base_url}")
    except Exception as e:
        print(f"خطأ في تحميل الإعدادات: {e}")
```

---

## ✅ قائمة التحقق

- [ ] حصلت على رابط Tunnel
- [ ] حدثت API URL في main.py
- [ ] شغّلت التطبيق
- [ ] اختبرت الاتصال
- [ ] اختبرت من شبكة مختلفة

---

## 🎯 النتيجة

بعد التحديث:
- ✅ يمكنك الوصول من أي شبكة
- ✅ الرابط آمن (HTTPS)
- ✅ لا تحتاج فتح منافذ

---

**بالتوفيق! 🚀**
