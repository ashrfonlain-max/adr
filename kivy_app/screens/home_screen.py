"""
الشاشة الرئيسية
"""

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.gridlayout import MDGridLayout


class HomeScreen(MDScreen):
    """الشاشة الرئيسية"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()
    
    def build_ui(self):
        """بناء واجهة المستخدم"""
        layout = MDBoxLayout(
            orientation='vertical',
            padding=20,
            spacing=20
        )
        
        # العنوان
        title = MDLabel(
            text="الصفحة الرئيسية",
            halign="center",
            theme_text_color="Primary",
            font_style="H4"
        )
        layout.add_widget(title)
        
        # بطاقات الإحصائيات
        stats_layout = MDGridLayout(
            cols=2,
            spacing=10,
            size_hint_y=None,
            height=200
        )
        
        # بطاقة الطلبات المستلمة
        received_card = MDCard(
            orientation='vertical',
            padding=20,
            spacing=10,
            size_hint_y=None,
            height=100
        )
        received_card.add_widget(MDLabel(
            text="الطلبات المستلمة",
            halign="center",
            theme_text_color="Primary"
        ))
        self.received_count = MDLabel(
            text="0",
            halign="center",
            font_style="H4"
        )
        received_card.add_widget(self.received_count)
        stats_layout.add_widget(received_card)
        
        # بطاقة الطلبات قيد الإصلاح
        repairing_card = MDCard(
            orientation='vertical',
            padding=20,
            spacing=10,
            size_hint_y=None,
            height=100
        )
        repairing_card.add_widget(MDLabel(
            text="قيد الإصلاح",
            halign="center",
            theme_text_color="Primary"
        ))
        self.repairing_count = MDLabel(
            text="0",
            halign="center",
            font_style="H4"
        )
        repairing_card.add_widget(self.repairing_count)
        stats_layout.add_widget(repairing_card)
        
        layout.add_widget(stats_layout)
        
        # الأزرار الرئيسية
        buttons_layout = MDBoxLayout(
            orientation='vertical',
            spacing=10,
            size_hint_y=None,
            height=200
        )
        
        # زر عرض الطلبات
        jobs_btn = MDRaisedButton(
            text="عرض جميع الطلبات",
            size_hint_y=None,
            height=50,
            on_release=self.show_jobs
        )
        buttons_layout.add_widget(jobs_btn)
        
        # زر إضافة طلب جديد
        add_btn = MDRaisedButton(
            text="إضافة طلب جديد",
            size_hint_y=None,
            height=50,
            on_release=self.add_job
        )
        buttons_layout.add_widget(add_btn)
        
        # زر الإعدادات
        settings_btn = MDRaisedButton(
            text="الإعدادات",
            size_hint_y=None,
            height=50,
            on_release=self.show_settings
        )
        buttons_layout.add_widget(settings_btn)
        
        layout.add_widget(buttons_layout)
        
        self.add_widget(layout)
    
    def show_jobs(self, instance):
        """عرض قائمة الطلبات"""
        self.manager.current = 'jobs'
    
    def add_job(self, instance):
        """إضافة طلب جديد"""
        self.manager.current = 'add_job'
    
    def show_settings(self, instance):
        """عرض الإعدادات"""
        self.manager.current = 'settings'
    
    def on_enter(self):
        """عند دخول الشاشة"""
        # تحديث الإحصائيات
        self.update_stats()
    
    def update_stats(self):
        """تحديث الإحصائيات"""
        # يمكن جلب البيانات من API
        # self.received_count.text = str(received_count)
        # self.repairing_count.text = str(repairing_count)
        pass

