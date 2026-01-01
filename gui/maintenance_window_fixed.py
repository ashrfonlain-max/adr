"""
واجهة المستخدم الرئيسية لنظام إدارة الصيانة
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox
from datetime import datetime
from database.connection import get_db, init_db
from database.models import MaintenanceJob, Customer, Device, Part, Payment, User, Status
from services.maintenance_service import MaintenanceService
from services.code_service import CodeService
from utils.barcode_generator import BarcodeGenerator
from utils.notification_service import NotificationService

class MaintenanceFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        # الحصول على اتصال قاعدة البيانات
        self.db = next(get_db())
        
        # الحصول على مسار قاعدة البيانات من الإعدادات
        from config import DATABASE_URL
        db_path = DATABASE_URL.replace('sqlite:///', '')
        
        self.code_service = CodeService(db_path)
        self.maintenance_service = MaintenanceService(self.db)
        self.barcode_generator = BarcodeGenerator()
        self.notification_service = NotificationService({})  # سيتم تحميل الإعدادات من ملف التكوين
        
        # إعداد واجهة المستخدم
        self.setup_ui()
        
        # إنشاء المحتوى الرئيسي
        self.create_main_content()
        
        # إنشاء شريط الحالة
        self.create_status_bar()
        
        # تحميل البيانات
        self.load_data()

    # ... (الوظائف الأخرى تبقى كما هي)

    def quick_save(self):
        """إدخال سريع لطلب صيانة جديد"""
        try:
            # إنشاء نافذة الحوار
            dialog = ctk.CTkToplevel(self)
            dialog.title("إضافة طلب صيانة جديد")
            dialog.geometry("500x700")
            
            # جعل النافذة في المقدمة
            dialog.transient(self)
            dialog.grab_set()
            
            # إطار التمرير للمحتوى
            content = ctk.CTkScrollableFrame(dialog)
            content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # عنوان النموذج
            title_label = ctk.CTkLabel(
                content, 
                text="نموذج إضافة طلب صيانة جديد",
                font=("Arial", 16, "bold")
            )
            title_label.pack(pady=(0, 20))
            
            # توليد كود فريد
            next_code = self.code_service.generate_unique_code()
            
            # دالة لتحديث الكود
            def update_code():
                nonlocal next_code
                next_code = self.code_service.generate_unique_code()
                code_label.configure(text=next_code)
                barcode_entry.delete(0, tk.END)
                barcode_entry.insert(0, next_code)
                return next_code
            
            # إطار عرض الكود
            code_frame = ctk.CTkFrame(content, fg_color="#e3f2fd", corner_radius=10)
            code_frame.pack(fill=tk.X, pady=(0, 20), padx=10)
            
            # عرض الكود
            code_label = ctk.CTkLabel(
                code_frame, 
                text=next_code, 
                font=("Arial", 24, "bold"), 
                text_color="#0d47a1"
            )
            code_label.pack(pady=15)
            
            # زر تحديث الكود
            ctk.CTkButton(
                code_frame,
                text="تحديث الكود",
                command=update_code,
                width=120,
                height=30,
                fg_color="#1976d2",
                hover_color="#1565c0"
            ).pack(pady=(0, 10))
            
            # حقول الإدخال
            fields_frame = ctk.CTkFrame(content, fg_color="transparent")
            fields_frame.pack(fill=tk.BOTH, expand=True)
            
            # حقل الباركود
            ctk.CTkLabel(fields_frame, text="باركود/رقم تسلسلي:", font=("Arial", 12)).pack(anchor="w")
            barcode_entry = ctk.CTkEntry(fields_frame, placeholder_text="سيتم ملؤه تلقائياً")
            barcode_entry.insert(0, next_code)
            barcode_entry.pack(fill=tk.X, pady=(0, 10))
            
            # حقل اسم العميل
            ctk.CTkLabel(fields_frame, text="اسم العميل:", font=("Arial", 12)).pack(anchor="w")
            customer_entry = ctk.CTkEntry(fields_frame, placeholder_text="اسم العميل بالكامل")
            customer_entry.pack(fill=tk.X, pady=(0, 10))
            
            # حقل رقم الهاتف
            ctk.CTkLabel(fields_frame, text="رقم الهاتف:", font=("Arial", 12)).pack(anchor="w")
            phone_entry = ctk.CTkEntry(fields_frame, placeholder_text="05xxxxxxxx")
            phone_entry.pack(fill=tk.X, pady=(0, 10))
            
            # حقل نوع الجهاز
            ctk.CTkLabel(fields_frame, text="نوع الجهاز:", font=("Arial", 12)).pack(anchor="w")
            device_type_entry = ctk.CTkEntry(fields_frame, placeholder_text="مثال: جوال سامسونج")
            device_type_entry.pack(fill=tk.X, pady=(0, 10))
            
            # حقل وصف العطل
            ctk.CTkLabel(fields_frame, text="وصف العطل:", font=("Arial", 12)).pack(anchor="w")
            issue_text = ctk.CTkTextbox(fields_frame, height=100)
            issue_text.pack(fill=tk.X, pady=(0, 20))
            
            # دالة البحث عن العميل
            def search_customer():
                customer_name = customer_entry.get().strip()
                if customer_name:
                    try:
                        db = next(get_db())
                        from database.models import Customer
                        customer = db.query(Customer).filter(
                            Customer.name.ilike(f"%{customer_name}%")
                        ).first()
                        
                        if customer:
                            phone_entry.delete(0, tk.END)
                            phone_entry.insert(0, customer.phone)
                            device_type_entry.focus_set()
                            return True
                    except Exception as e:
                        print(f"خطأ في البحث عن العميل: {e}")
                return False
            
            # دالة الحفظ
            def save():
                try:
                    # جمع البيانات
                    customer_name = customer_entry.get().strip()
                    phone = phone_entry.get().strip()
                    device_type = device_type_entry.get().strip()
                    barcode = barcode_entry.get().strip() or next_code
                    issue = issue_text.get("1.0", tk.END).strip() or "لم يتم تحديد وصف العطل"
                    
                    # التحقق من الحقول المطلوبة
                    if not customer_name:
                        messagebox.showwarning("حقل مطلوب", "الرجاء إدخال اسم العميل")
                        customer_entry.focus_set()
                        return
                        
                    if not phone:
                        messagebox.showwarning("حقل مطلوب", "الرجاء إدخال رقم الهاتف")
                        phone_entry.focus_set()
                        return
                        
                    if not device_type:
                        messagebox.showwarning("حقل مطلوب", "الرجاء إدخال نوع الجهاز")
                        device_type_entry.focus_set()
                        return
                    
                    # حفظ البيانات
                    success, message, job = self.maintenance_service.create_maintenance_job(
                        customer_name=customer_name,
                        phone=phone,
                        device_type=device_type,
                        device_model="غير محدد",
                        serial_number=barcode,
                        issue_description=issue
                    )
                    
                    if success:
                        # تحديث بيانات الجهاز
                        try:
                            device_data = {
                                'serial_number': barcode,
                                'barcode': barcode,
                                'device_type': device_type,
                                'device_model': "غير محدد",
                                'customer_name': customer_name
                            }
                            self.code_service.save_device_code(device_data)
                        except Exception as e:
                            print(f"⚠️ تحذير: {e}")
                        
                        messagebox.showinfo("نجاح", f"تم حفظ الطلب بنجاح\nرقم التتبع: {job['tracking_code']}")
                        self.load_data()
                        
                        # تحديث الكود التالي
                        update_code()
                        
                        # مسح الحقول
                        customer_entry.delete(0, tk.END)
                        phone_entry.delete(0, tk.END)
                        device_type_entry.delete(0, tk.END)
                        issue_text.delete("1.0", tk.END)
                        
                        # التركيز على حقل اسم العميل للطلب التالي
                        customer_entry.focus()
                    else:
                        messagebox.showerror("خطأ", f"فشل في الحفظ: {message}")
                        
                except Exception as e:
                    messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
            
            # ربط الأحداث للانتقال باستخدام زر Enter
            def bind_enter_navigation(widget, next_widget=None, submit=False, before_next=None):
                def handler(event):
                    try:
                        if isinstance(widget, ctk.CTkTextbox) and (event.state & 0x0001):
                            # السماح باستخدام Shift+Enter لإضافة سطر جديد داخل مربع النص
                            return
                    except Exception:
                        pass
                    
                    if before_next:
                        try:
                            before_next()
                        except Exception as nav_error:
                            print(f"⚠️ تحذير أثناء before_next: {nav_error}")
                    
                    if submit:
                        save_btn.focus_set()
                        save()
                    elif next_widget:
                        next_widget.focus_set()
                        if isinstance(next_widget, ctk.CTkTextbox):
                            next_widget.focus()
                    return "break"
                
                widget.bind('<Return>', handler)
                widget.bind('<KeyPress-Return>', handler)
            
            bind_enter_navigation(barcode_entry, customer_entry)
            bind_enter_navigation(customer_entry, phone_entry, before_next=search_customer)
            bind_enter_navigation(phone_entry, device_type_entry)
            bind_enter_navigation(device_type_entry, issue_text)
            bind_enter_navigation(issue_text, submit=True)
            
            # أزرار الحفظ والإلغاء
            btn_frame = ctk.CTkFrame(content, fg_color="transparent")
            btn_frame.pack(fill=tk.X, pady=10)
            
            ctk.CTkButton(
                btn_frame,
                text="💾 حفظ",
                command=save,
                fg_color="#28a745",
                hover_color="#218838",
                height=40,
                font=("Arial", 14, "bold")
            ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            ctk.CTkButton(
                btn_frame,
                text="❌ إلغاء",
                command=dialog.destroy,
                fg_color="#dc3545",
                hover_color="#c82333",
                height=40,
                font=("Arial", 14)
            ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            # التركيز على حقل الباركود
            barcode_entry.focus_set()
            
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ: {str(e)}")
            import traceback
            traceback.print_exc()

    # ... (بقية الوظائف تبقى كما هي)

if __name__ == "__main__":
    app = ctk.CTk()
    app.title("نظام إدارة الصيانة")
    app.geometry("1200x800")
    
    # تهيئة قاعدة البيانات
    init_db()
    
    # إنشاء النافذة الرئيسية
    frame = MaintenanceFrame(app)
    frame.pack(fill=tk.BOTH, expand=True)
    
    app.mainloop()
