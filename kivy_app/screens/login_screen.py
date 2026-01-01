"""
شاشة تسجيل الدخول
"""

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivy.clock import Clock
from services.api_service import APIService


class LoginScreen(MDScreen):
    """شاشة تسجيل الدخول"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_service = None
        self.build_ui()
    
    def get_api_service(self):
        """الحصول على API Service مع الرابط الصحيح"""
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        if app and not self.api_service:
            self.api_service = APIService(base_url=app.api_base_url)
        elif not self.api_service:
            self.api_service = APIService()
        return self.api_service
    
    def build_ui(self):
        """بناء واجهة المستخدم"""
        layout = MDBoxLayout(
            orientation='vertical',
            padding=40,
            spacing=20,
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        
        # العنوان
        title = MDLabel(
            text="نظام إدارة الصيانة",
            halign="center",
            theme_text_color="Primary",
            font_style="H4"
        )
        layout.add_widget(title)
        
        # حقل عنوان الخادم
        self.server_field = MDTextField(
            hint_text="عنوان الخادم (مثال: http://localhost:5000)",
            mode="fill",
            size_hint_y=None,
            height=50,
            text="http://localhost:5000"
        )
        layout.add_widget(self.server_field)
        
        # حقل كلمة المرور
        self.password_field = MDTextField(
            hint_text="كلمة المرور",
            mode="fill",
            password=True,
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.password_field)
        
        # زر تسجيل الدخول
        login_btn = MDRaisedButton(
            text="تسجيل الدخول",
            size_hint_y=None,
            height=50,
            on_release=self.login
        )
        layout.add_widget(login_btn)
        
        # رسالة الخطأ
        self.error_label = MDLabel(
            text="",
            halign="center",
            theme_text_color="Error",
            size_hint_y=None,
            height=30
        )
        layout.add_widget(self.error_label)
        
        self.add_widget(layout)
    
    def login(self, instance):
        """تسجيل الدخول"""
        server_url = self.server_field.text.strip()
        password = self.password_field.text
        
        if not server_url or not password:
            self.error_label.text = "يرجى إدخال عنوان الخادم وكلمة المرور"
            return
        
        # تحديث عنوان API
        if not server_url.endswith('/api'):
            if server_url.endswith('/'):
                self.api_service.base_url = f"{server_url}api"
            else:
                self.api_service.base_url = f"{server_url}/api"
        else:
            self.api_service.base_url = server_url
        
        # تحديث عنوان API في التطبيق
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        if app:
            app.api_base_url = self.api_service.base_url
            # تحديث API Service في التطبيق
            self.api_service = APIService(base_url=app.api_base_url)
        
        # محاولة تسجيل الدخول
        api_service = self.get_api_service()
        success, message, user = api_service.login(password)
        
        if success:
            # حفظ معلومات المستخدم
            if app:
                app.current_user = user
            # حفظ الإعدادات
            self.save_settings(server_url, password)
            # الانتقال للشاشة الرئيسية
            self.manager.current = 'home'
            self.error_label.text = ""
        else:
            self.error_label.text = message or "فشل تسجيل الدخول"
    
    def save_settings(self, server_url: str, password: str):
        """حفظ الإعدادات"""
        try:
            import json
            import os
            from kivy.storage.jsonstore import JsonStore
            
            store = JsonStore('settings.json')
            store.put('server_url', value=server_url)
            store.put('password', value=password)
        except Exception as e:
            print(f"خطأ في حفظ الإعدادات: {e}")

