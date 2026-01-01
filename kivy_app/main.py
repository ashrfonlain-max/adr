"""
تطبيق Android بـ Kivy/KivyMD
نظام إدارة الصيانة - ADR Maintenance System
"""

from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivy.core.window import Window

# استيراد الشاشات
from screens.login_screen import LoginScreen
from screens.home_screen import HomeScreen
from screens.jobs_screen import JobsScreen
from screens.add_job_screen import AddJobScreen
from screens.job_details_screen import JobDetailsScreen
from screens.settings_screen import SettingsScreen

# إعدادات النافذة (للتطوير)
Window.size = (360, 640)  # حجم هاتف Android قياسي


class MaintenanceApp(MDApp):
    """التطبيق الرئيسي"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"
        self.current_user = None
        # الرابط الافتراضي - يمكن تغييره من الإعدادات
        self.api_base_url = "http://localhost:5000/api"
        
    def build(self):
        """بناء واجهة التطبيق"""
        # إنشاء Screen Manager
        sm = MDScreenManager()
        
        # إضافة الشاشات
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(JobsScreen(name='jobs'))
        sm.add_widget(AddJobScreen(name='add_job'))
        sm.add_widget(JobDetailsScreen(name='job_details'))
        sm.add_widget(SettingsScreen(name='settings'))
        
        return sm
    
    def on_start(self):
        """عند بدء التطبيق"""
        # تحميل إعدادات السيرفر
        self.load_server_settings()
    
    def load_server_settings(self):
        """تحميل إعدادات السيرفر من الملف"""
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
                print(f"✅ تم تحميل رابط السيرفر: {self.api_base_url}")
            else:
                print("ℹ️  استخدام الرابط الافتراضي. يمكنك تغييره من الإعدادات.")
        except Exception as e:
            print(f"⚠️  خطأ في تحميل الإعدادات: {e}")
            print(f"   استخدام الرابط الافتراضي: {self.api_base_url}")
    
    def save_server_url(self, url: str):
        """حفظ رابط السيرفر"""
        try:
            from kivy.storage.jsonstore import JsonStore
            store = JsonStore('settings.json')
            store.put('server_url', value=url)
            
            # تحديث الرابط الحالي
            if not url.endswith('/api'):
                if url.endswith('/'):
                    self.api_base_url = f"{url}api"
                else:
                    self.api_base_url = f"{url}/api"
            else:
                self.api_base_url = url
            
            print(f"✅ تم حفظ رابط السيرفر: {self.api_base_url}")
            return True
        except Exception as e:
            print(f"❌ خطأ في حفظ الإعدادات: {e}")
            return False


if __name__ == '__main__':
    MaintenanceApp().run()

