"""
شاشة تفاصيل الطلب
"""

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from services.api_service import APIService


class JobDetailsScreen(MDScreen):
    """شاشة تفاصيل الطلب"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_service = None
        self.current_job = None
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
        scroll = MDScrollView()
        layout = MDBoxLayout(
            orientation='vertical',
            padding=20,
            spacing=15,
            size_hint_y=None
        )
        layout.bind(minimum_height=layout.setter('height'))
        
        # العنوان
        self.title_label = MDLabel(
            text="تفاصيل الطلب",
            halign="center",
            theme_text_color="Primary",
            font_style="H4",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.title_label)
        
        # معلومات الطلب
        self.info_layout = MDBoxLayout(
            orientation='vertical',
            spacing=10,
            size_hint_y=None
        )
        layout.add_widget(self.info_layout)
        
        # الأزرار
        buttons_layout = MDBoxLayout(
            orientation='vertical',
            spacing=10,
            size_hint_y=None,
            height=200
        )
        
        # زر تحديث الحالة
        self.update_status_btn = MDRaisedButton(
            text="تحديث الحالة",
            size_hint_y=None,
            height=50,
            on_release=self.update_status
        )
        buttons_layout.add_widget(self.update_status_btn)
        
        # زر تعديل
        edit_btn = MDRaisedButton(
            text="تعديل",
            size_hint_y=None,
            height=50,
            on_release=self.edit_job
        )
        buttons_layout.add_widget(edit_btn)
        
        # زر العودة
        back_btn = MDRaisedButton(
            text="العودة",
            size_hint_y=None,
            height=50,
            on_release=self.go_back
        )
        buttons_layout.add_widget(back_btn)
        
        layout.add_widget(buttons_layout)
        
        scroll.add_widget(layout)
        self.add_widget(scroll)
    
    def on_enter(self):
        """عند دخول الشاشة"""
        if self.current_job:
            self.display_job_details()
    
    def display_job_details(self):
        """عرض تفاصيل الطلب"""
        self.info_layout.clear_widgets()
        
        job = self.current_job
        
        # كود التتبع
        self.add_info("كود التتبع", job.get('tracking_code', 'N/A'))
        
        # اسم العميل
        self.add_info("اسم العميل", job.get('customer_name', 'N/A'))
        
        # رقم الهاتف
        self.add_info("رقم الهاتف", job.get('phone', 'N/A'))
        
        # نوع الجهاز
        self.add_info("نوع الجهاز", job.get('device_type', 'N/A'))
        
        # موديل الجهاز
        self.add_info("موديل الجهاز", job.get('device_model', 'N/A'))
        
        # رقم السيريال
        self.add_info("رقم السيريال", job.get('serial_number', 'N/A'))
        
        # الحالة
        self.add_info("الحالة", job.get('status', 'N/A'))
        
        # التكلفة
        self.add_info("التكلفة", f"{job.get('final_cost', job.get('estimated_cost', 0))} {job.get('currency', 'USD')}")
    
    def add_info(self, label, value):
        """إضافة معلومة"""
        info_layout = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=40
        )
        
        label_widget = MDLabel(
            text=f"{label}:",
            theme_text_color="Primary",
            size_hint_x=0.4
        )
        info_layout.add_widget(label_widget)
        
        value_widget = MDLabel(
            text=str(value),
            theme_text_color="Secondary",
            size_hint_x=0.6
        )
        info_layout.add_widget(value_widget)
        
        self.info_layout.add_widget(info_layout)
    
    def update_status(self, instance):
        """تحديث حالة الطلب"""
        # يمكن فتح نافذة منبثقة لتحديث الحالة
        pass
    
    def edit_job(self, instance):
        """تعديل الطلب"""
        # يمكن الانتقال لشاشة التعديل
        pass
    
    def go_back(self, instance):
        """العودة"""
        self.manager.current = 'jobs'






