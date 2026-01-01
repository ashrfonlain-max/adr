"""
شاشة قائمة الطلبات
"""

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFloatingActionButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from services.api_service import APIService


class JobsScreen(MDScreen):
    """شاشة قائمة الطلبات"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_service = None
        self.jobs = []
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
            padding=10,
            spacing=10
        )
        
        # شريط البحث
        search_layout = MDBoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=50,
            spacing=10
        )
        
        self.search_field = MDTextField(
            hint_text="بحث...",
            mode="fill",
            size_hint_x=0.8
        )
        search_layout.add_widget(self.search_field)
        
        search_btn = MDIconButton(
            icon="magnify",
            on_release=self.search_jobs
        )
        search_layout.add_widget(search_btn)
        
        layout.add_widget(search_layout)
        
        # قائمة الطلبات
        scroll = MDScrollView()
        self.jobs_layout = MDBoxLayout(
            orientation='vertical',
            spacing=10,
            size_hint_y=None
        )
        self.jobs_layout.bind(minimum_height=self.jobs_layout.setter('height'))
        scroll.add_widget(self.jobs_layout)
        layout.add_widget(scroll)
        
        # زر إضافة جديد
        fab = MDFloatingActionButton(
            icon="plus",
            pos_hint={'right': 0.95, 'y': 0.05},
            on_release=self.add_job
        )
        layout.add_widget(fab)
        
        self.add_widget(layout)
    
    def on_enter(self):
        """عند دخول الشاشة"""
        self.load_jobs()
    
    def load_jobs(self):
        """تحميل الطلبات"""
        # جلب الطلبات من API
        api_service = self.get_api_service()
        success, jobs = api_service.get_jobs()
        
        if success:
            self.jobs = jobs
            self.display_jobs()
        else:
            # عرض رسالة خطأ
            pass
    
    def display_jobs(self):
        """عرض الطلبات"""
        self.jobs_layout.clear_widgets()
        
        for job in self.jobs:
            card = self.create_job_card(job)
            self.jobs_layout.add_widget(card)
    
    def create_job_card(self, job):
        """إنشاء بطاقة طلب"""
        card = MDCard(
            orientation='vertical',
            padding=15,
            spacing=10,
            size_hint_y=None,
            height=120,
            on_release=lambda x, j=job: self.show_job_details(j)
        )
        
        # معلومات الطلب
        title = MDLabel(
            text=f"#{job.get('tracking_code', 'N/A')} - {job.get('customer_name', 'N/A')}",
            theme_text_color="Primary",
            font_style="H6"
        )
        card.add_widget(title)
        
        device_info = MDLabel(
            text=f"{job.get('device_type', 'N/A')} - {job.get('device_model', 'N/A')}",
            theme_text_color="Secondary"
        )
        card.add_widget(device_info)
        
        status = MDLabel(
            text=f"الحالة: {job.get('status', 'N/A')}",
            theme_text_color="Primary"
        )
        card.add_widget(status)
        
        return card
    
    def show_job_details(self, job):
        """عرض تفاصيل الطلب"""
        # حفظ الطلب الحالي
        self.manager.get_screen('job_details').current_job = job
        self.manager.current = 'job_details'
    
    def search_jobs(self, instance):
        """بحث في الطلبات"""
        query = self.search_field.text
        # تنفيذ البحث
        api_service = self.get_api_service()
        success, jobs = api_service.get_jobs(search=query if query else None)
        if success:
            self.jobs = jobs
            self.display_jobs()
    
    def add_job(self, instance):
        """إضافة طلب جديد"""
        self.manager.current = 'add_job'

