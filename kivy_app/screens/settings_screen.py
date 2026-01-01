"""
شاشة الإعدادات
"""

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivy.storage.jsonstore import JsonStore


class SettingsScreen(MDScreen):
    """شاشة الإعدادات"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.store = JsonStore('settings.json')
        self.build_ui()
        self.load_settings()
    
    def build_ui(self):
        """بناء واجهة المستخدم"""
        scroll = MDScrollView()
        layout = MDBoxLayout(
            orientation='vertical',
            padding=20,
            spacing=15,
            size_hint_y=None
        )
        layout.bind(minimum_height=layout.setter('height'))
        
        # العنوان
        title = MDLabel(
            text="الإعدادات",
            halign="center",
            theme_text_color="Primary",
            font_style="H4",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(title)
        
        # حقل عنوان الخادم
        self.server_field = MDTextField(
            hint_text="عنوان الخادم",
            mode="fill",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.server_field)
        
        # زر حفظ
        save_btn = MDRaisedButton(
            text="حفظ",
            size_hint_y=None,
            height=50,
            on_release=self.save_settings
        )
        layout.add_widget(save_btn)
        
        # زر تسجيل الخروج
        logout_btn = MDRaisedButton(
            text="تسجيل الخروج",
            size_hint_y=None,
            height=50,
            on_release=self.logout
        )
        layout.add_widget(logout_btn)
        
        scroll.add_widget(layout)
        self.add_widget(scroll)
    
    def load_settings(self):
        """تحميل الإعدادات"""
        try:
            if 'server_url' in self.store:
                self.server_field.text = self.store.get('server_url')['value']
        except Exception as e:
            print(f"خطأ في تحميل الإعدادات: {e}")
    
    def save_settings(self, instance):
        """حفظ الإعدادات"""
        try:
            from kivymd.app import MDApp
            app = MDApp.get_running_app()
            
            server_url = self.server_field.text.strip()
            if server_url:
                self.store.put('server_url', value=server_url)
                # تحديث عنوان API
                if app:
                    if not server_url.endswith('/api'):
                        if server_url.endswith('/'):
                            app.api_base_url = f"{server_url}api"
                        else:
                            app.api_base_url = f"{server_url}/api"
                    else:
                        app.api_base_url = server_url
                    
                    # استخدام دالة save_server_url من التطبيق
                    app.save_server_url(server_url)
                
                # عرض رسالة نجاح
                from kivymd.uix.snackbar import Snackbar
                Snackbar(text="تم حفظ الإعدادات بنجاح").show()
        except Exception as e:
            print(f"خطأ في حفظ الإعدادات: {e}")
    
    def logout(self, instance):
        """تسجيل الخروج"""
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        if app:
            app.current_user = None
        self.manager.current = 'login'






