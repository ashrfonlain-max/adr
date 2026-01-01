"""
شاشة إضافة طلب جديد
"""

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from services.api_service import APIService


class AddJobScreen(MDScreen):
    """شاشة إضافة طلب جديد"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_service = APIService()
        self.build_ui()
    
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
            text="إضافة طلب جديد",
            halign="center",
            theme_text_color="Primary",
            font_style="H4",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(title)
        
        # اسم العميل
        self.customer_name_field = MDTextField(
            hint_text="اسم العميل *",
            mode="fill",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.customer_name_field)
        
        # رقم الهاتف
        self.phone_field = MDTextField(
            hint_text="رقم الهاتف *",
            mode="fill",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.phone_field)
        
        # نوع الجهاز
        self.device_type_field = MDTextField(
            hint_text="نوع الجهاز *",
            mode="fill",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.device_type_field)
        
        # موديل الجهاز
        self.device_model_field = MDTextField(
            hint_text="موديل الجهاز",
            mode="fill",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.device_model_field)
        
        # رقم السيريال
        self.serial_number_field = MDTextField(
            hint_text="رقم السيريال",
            mode="fill",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.serial_number_field)
        
        # وصف العطل
        self.issue_field = MDTextField(
            hint_text="وصف العطل",
            mode="fill",
            multiline=True,
            size_hint_y=None,
            height=100
        )
        layout.add_widget(self.issue_field)
        
        # التكلفة التقديرية
        self.estimated_cost_field = MDTextField(
            hint_text="التكلفة التقديرية",
            mode="fill",
            size_hint_y=None,
            height=50
        )
        layout.add_widget(self.estimated_cost_field)
        
        # رسالة الخطأ
        self.error_label = MDLabel(
            text="",
            halign="center",
            theme_text_color="Error",
            size_hint_y=None,
            height=30
        )
        layout.add_widget(self.error_label)
        
        # زر الحفظ
        save_btn = MDRaisedButton(
            text="حفظ",
            size_hint_y=None,
            height=50,
            on_release=self.save_job
        )
        layout.add_widget(save_btn)
        
        # زر الإلغاء
        cancel_btn = MDRaisedButton(
            text="إلغاء",
            size_hint_y=None,
            height=50,
            on_release=self.cancel
        )
        layout.add_widget(cancel_btn)
        
        scroll.add_widget(layout)
        self.add_widget(scroll)
    
    def save_job(self, instance):
        """حفظ الطلب"""
        # التحقق من الحقول المطلوبة
        if not self.customer_name_field.text or not self.phone_field.text or not self.device_type_field.text:
            self.error_label.text = "يرجى ملء جميع الحقول المطلوبة"
            return
        
        # إعداد البيانات
        data = {
            'customer_name': self.customer_name_field.text,
            'phone': self.phone_field.text,
            'device_type': self.device_type_field.text,
            'device_model': self.device_model_field.text or '',
            'serial_number': self.serial_number_field.text or '',
            'issue_description': self.issue_field.text or '',
            'estimated_cost': float(self.estimated_cost_field.text or 0)
        }
        
        # إرسال الطلب
        api_service = self.get_api_service()
        success, message, job = api_service.create_job(data)
        
        if success:
            # العودة للشاشة السابقة
            self.manager.current = 'jobs'
            self.clear_fields()
        else:
            self.error_label.text = message or "فشل إضافة الطلب"
    
    def clear_fields(self):
        """مسح الحقول"""
        self.customer_name_field.text = ""
        self.phone_field.text = ""
        self.device_type_field.text = ""
        self.device_model_field.text = ""
        self.serial_number_field.text = ""
        self.issue_field.text = ""
        self.estimated_cost_field.text = ""
        self.error_label.text = ""
    
    def cancel(self, instance):
        """إلغاء"""
        self.manager.current = 'jobs'






