"""
واجهة المستخدم الرئيسية لنظام إدارة الصيانة
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from datetime import datetime
from services.maintenance_service import MaintenanceService
from services.code_service import CodeService
from database.connection import get_db
from utils.barcode_generator import BarcodeGenerator
from utils.notification_service import NotificationService
from config import UPLOAD_FOLDER, TEMP_FOLDER

class MaintenanceFrame(ctk.CTkFrame):
    """إطار إدارة طلبات الصيانة"""
    
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
    
    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        # تكوين الشبكة
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # شريط الأدوات
        toolbar = ctk.CTkFrame(self, height=50, fg_color=("gray90", "gray16"))
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        # أزرار شريط الأدوات
        btn_add = ctk.CTkButton(toolbar, text="إدخال سريع", command=self.quick_save)
        btn_add.pack(side=tk.RIGHT, padx=5)
        
        btn_edit = ctk.CTkButton(toolbar, text="تعديل", command=self.edit_maintenance)
        btn_edit.pack(side=tk.RIGHT, padx=5)
        
        btn_delete = ctk.CTkButton(toolbar, text="حذف", command=self.delete_maintenance, fg_color="#d32f2f", hover_color="#b71c1c")
        btn_delete.pack(side=tk.RIGHT, padx=5)
        
        btn_refresh = ctk.CTkButton(toolbar, text="تحديث", command=self.load_data)
        btn_refresh.pack(side=tk.LEFT, padx=5)
        
        # حقل البحث
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.search_maintenance())
        
        search_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        search_frame.pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(search_frame, text="بحث:").pack(side=tk.LEFT, padx=5)
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, width=200)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # ربط Enter في حقل البحث لتنفيذ البحث
        search_entry.bind('<Return>', lambda e: self.search_maintenance())
    
    def create_main_content(self):
        """إنشاء منطقة المحتوى الرئيسي"""
        # إنشاء إطار رئيسي للمحتوى
        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)
        
        # إنشاء علامات التبويب
        self.tabview = ctk.CTkTabview(content_frame)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # إضافة علامات التبويب
        self.tabview.add("قائمة الطلبات")
        self.tabview.add("إحصائيات")
        self.tabview.add("التقارير")
        
        # تكوين علامة التبويب الأولى (قائمة الطلبات)
        self.setup_requests_tab()
        
        # تكوين علامة التبويب الثانية (الإحصائيات)
        self.setup_stats_tab()
        
        # تكوين علامة التبويب الثالثة (التقارير)
        self.setup_reports_tab()
    
    def setup_requests_tab(self):
        """إعداد علامة تبويب قائمة الطلبات"""
        tab = self.tabview.tab("قائمة الطلبات")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        # إنشاء Treeview لعرض الطلبات
        columns = ("id", "tracking_code", "customer_name", "device_type", "status", "received_date")
        self.tree = ttk.Treeview(
            tab, 
            columns=columns, 
            show="headings",
            selectmode="browse"
        )
        
        # تكوين العناوين
        self.tree.heading("id", text="#")
        self.tree.heading("tracking_code", text="رقم التتبع")
        self.tree.heading("customer_name", text="اسم العميل")
        self.tree.heading("device_type", text="نوع الجهاز")
        self.tree.heading("status", text="الحالة")
        self.tree.heading("received_date", text="تاريخ الاستلام")
        
        # تكوين عرض الأعمدة
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("id", width=50, anchor=tk.CENTER)
        self.tree.column("tracking_code", width=120, anchor=tk.CENTER)
        self.tree.column("customer_name", width=200, anchor=tk.CENTER)
        self.tree.column("device_type", width=150, anchor=tk.CENTER)
        self.tree.column("status", width=120, anchor=tk.CENTER)
        self.tree.column("received_date", width=120, anchor=tk.CENTER)
        
        # إضافة شريط التمرير
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        # تعبئة واجهة المستخدم
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # ربط حدث النقر المزدوج
        self.tree.bind("<Double-1>", self.on_item_double_click)
    
    def setup_stats_tab(self):
        """إعداد علامة تبويب الإحصائيات"""
        tab = self.tabview.tab("إحصائيات")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        # إضافة عناصر واجهة المستخدم للإحصائيات
        stats_frame = ctk.CTkFrame(tab)
        stats_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # إضافة بطاقات الإحصائيات
        self.stats_cards = {}
        stats = [
            ("إجمالي الطلبات", "0", "#2196F3"),
            ("قيد المعالجة", "0", "#FFC107"),
            ("جاهزة للتسليم", "0", "#4CAF50"),
            ("تم التسليم", "0", "#9C27B0")
        ]
        
        for i, (title, value, color) in enumerate(stats):
            card = ctk.CTkFrame(stats_frame, fg_color=color, corner_radius=10)
            card.grid(row=0, column=i, padx=10, pady=10, sticky="nsew")
            
            ctk.CTkLabel(
                card, 
                text=value, 
                font=("Arial", 24, "bold"),
                text_color="white"
            ).pack(padx=20, pady=(15, 5))
            
            ctk.CTkLabel(
                card, 
                text=title,
                text_color="white"
            ).pack(padx=20, pady=(0, 15))
            
            self.stats_cards[title] = card
        
        # إضافة رسم بياني (سيتم تنفيذه لاحقاً)
        chart_frame = ctk.CTkFrame(tab)
        chart_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(
            chart_frame,
            text="إحصائيات الطلبات حسب الشهر",
            font=("Arial", 14, "bold")
        ).pack(pady=10)
    
    def setup_reports_tab(self):
        """إعداد علامة تبويب التقارير"""
        tab = self.tabview.tab("التقارير")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # أزرار إنشاء التقارير
        reports_toolbar = ctk.CTkFrame(tab)
        reports_toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkButton(
            reports_toolbar, 
            text="تقرير الطلبات",
            command=self.generate_orders_report
        ).pack(side=tk.RIGHT, padx=5)
        
        ctk.CTkButton(
            reports_toolbar,
            text="تقرير المدفوعات",
            command=self.generate_payments_report
        ).pack(side=tk.RIGHT, padx=5)
        
        # منطقة معاينة التقرير
        report_viewer = ctk.CTkFrame(tab)
        report_viewer.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        report_viewer.grid_columnconfigure(0, weight=1)
        report_viewer.grid_rowconfigure(0, weight=1)
        
        self.report_text = ctk.CTkTextbox(report_viewer, wrap=tk.WORD)
        self.report_text.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(
            report_viewer, 
            orient=tk.VERTICAL, 
            command=self.report_text.yview
        )
        self.report_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
    
    def create_status_bar(self):
        """إنشاء شريط الحالة"""
        status_bar = ctk.CTkFrame(self, height=25)
        status_bar.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        self.status_label = ctk.CTkLabel(status_bar, text="جاهز")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.status_count = ctk.CTkLabel(status_bar, text="0 عنصر")
        self.status_count.pack(side=tk.RIGHT, padx=10)
    
    def load_data(self):
        """تحميل بيانات الطلبات"""
        try:
            # مسح البيانات الحالية
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # جلب البيانات من الخدمة
            success, message, jobs = self.maintenance_service.search_jobs()
            
            if success:
                # إضافة البيانات إلى الجدول
                for job in jobs:
                    self.tree.insert("", tk.END, values=(
                        job['id'],
                        job['tracking_code'],
                        job['customer_name'],
                        job['device_type'],
                        job['status'],
                        job['received_at'].strftime('%Y-%m-%d') if job['received_at'] else ''
                    ))
                
                # تحديث العداد
                self.status_count.configure(text=f"{len(jobs)} عنصر")
                
                # تحديث الإحصائيات
                self.update_stats()
                
                return True
            else:
                messagebox.showerror("خطأ", f"فشل في تحميل البيانات: {message}")
                return False
                
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
            return False
    
    def update_stats(self):
        """تحديث إحصائيات الطلبات"""
        try:
            # جلب إحصائيات الطلبات
            success, message, stats = self.maintenance_service.get_dashboard_stats()
            
            if success:
                # تحديث البطاقات الإحصائية
                if 'total_jobs' in stats:
                    self.update_stat_card("إجمالي الطلبات", str(stats['total_jobs']))
                if 'in_progress' in stats:
                    self.update_stat_card("قيد المعالجة", str(stats['in_progress']))
                if 'ready_for_delivery' in stats:
                    self.update_stat_card("جاهزة للتسليم", str(stats['ready_for_delivery']))
                if 'delivered' in stats:
                    self.update_stat_card("تم التسليم", str(stats['delivered']))
                
                return True
            else:
                self.status_label.configure(text=f"خطأ في تحميل الإحصائيات: {message}")
                return False
                
        except Exception as e:
            self.status_label.configure(text=f"خطأ في تحديث الإحصائيات: {str(e)}")
            return False
    
    def update_stat_card(self, title, value):
        """تحديث قيمة بطاقة إحصائية"""
        if title in self.stats_cards:
            # الحصول على الإطار الأصلي
            card = self.stats_cards[title]
            
            # تدمير العناصر الحالية
            for widget in card.winfo_children():
                widget.destroy()
            
            # إضافة القيمة الجديدة
            ctk.CTkLabel(
                card, 
                text=value, 
                font=("Arial", 24, "bold"),
                text_color="white"
            ).pack(padx=20, pady=(15, 5))
            
            ctk.CTkLabel(
                card, 
                text=title,
                text_color="white"
            ).pack(padx=20, pady=(0, 15))
    
    def _search_device(self, code, customer_entry, device_type_combo, model_entry, serial_entry, barcode_entry):
        """البحث عن جهاز باستخدام الباركود أو الرقم التسلسلي"""
        if not code:
            return
            
        # البحث في قاعدة البيانات
        device = self.code_service.find_device_by_code(code)
        
        if device:
            # تعبئة الحقول ببيانات الجهاز
            customer_entry.delete(0, tk.END)
            customer_entry.insert(0, device.get('customer_name', ''))
            
            device_type_combo.set(device.get('device_type', ''))
            model_entry.delete(0, tk.END)
            model_entry.insert(0, device.get('device_model', ''))
            serial_entry.delete(0, tk.END)
            serial_entry.insert(0, device.get('device_serial', ''))
            
            # عرض رسالة للتنبيه بأنه تم العثور على الجهاز
            messagebox.showinfo(
                "تم العثور على الجهاز",
                f"تم العثور على جهاز مسجل مسبقاً\n"
                f"النوع: {device.get('device_type', 'غير محدد')}\n"
                f"الموديل: {device.get('device_model', 'غير محدد')}"
            )
        else:
            # إذا لم يتم العثور على الجهاز، إنشاء كود جديد
            barcode_entry.delete(0, tk.END)
            new_barcode = self.code_service.generate_unique_code()
            barcode_entry.insert(0, new_barcode)
            messagebox.showinfo(
                "جهاز جديد",
                f"لم يتم العثور على الجهاز. تم إنشاء كود جديد: {new_barcode}"
            )
    
    def _search_device(self, code, customer_entry=None, device_type_entry=None, model_entry=None, serial_entry=None, barcode_entry=None):
        """البحث عن جهاز باستخدام الباركود أو الرقم التسلسلي"""
        if not code:
            return
            
        # البحث في قاعدة البيانات
        device = self.code_service.find_device_by_code(code)
        
        if device:
            # تعبئة الحقول ببيانات الجهاز إذا تم توفيرها
            if customer_entry:
                customer_entry.delete(0, tk.END)
                customer_entry.insert(0, device.get('customer_name', ''))
            
            if device_type_entry:
                device_type_entry.delete(0, tk.END)
                device_type_entry.insert(0, device.get('device_type', ''))
                
            if model_entry:
                model_entry.delete(0, tk.END)
                model_entry.insert(0, device.get('device_model', ''))
                
            if serial_entry:
                serial_entry.delete(0, tk.END)
                serial_entry.insert(0, device.get('device_serial', ''))
            
            # عرض رسالة للتنبيه بأنه تم العثور على الجهاز
            messagebox.showinfo(
                "تم العثور على الجهاز",
                f"تم العثور على جهاز مسجل مسبقاً\n"
                f"النوع: {device.get('device_type', 'غير محدد')}\n"
                f"الموديل: {device.get('device_model', 'غير محدد')}"
            )
            return device
        
        return None

    
    def edit_maintenance(self):
        """تعديل طلب صيانة محدد"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("تحذير", "الرجاء اختيار طلب صيانة للتعديل")
            return
        
        # الحصول على معرف الطلب المحدد
        item = self.tree.item(selected[0])
        job_id = item['values'][0]
        
        # جلب بيانات الطلب
        success, message, job = self.maintenance_service.get_job_details(job_id)
        
        if not success:
            messagebox.showerror("خطأ", f"فشل في تحميل بيانات الطلب: {message}")
            return
        
        # إنشاء نافذة التعديل
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"تعديل طلب الصيانة #{job['tracking_code']}")
        dialog.geometry("700x600")
        dialog.grab_set()
        
        # محتوى النافذة
        content = ctk.CTkScrollableFrame(dialog)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # تبويبات التعديل
        tabview = ctk.CTkTabview(content)
        tabview.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # تبويب المعلومات الأساسية
        tab_info = tabview.add("المعلومات الأساسية")
        tab_status = tabview.add("حالة الطلب")
        tab_parts = tabview.add("قطع الغيار")
        tab_payments = tabview.add("المدفوعات")
        
        # تعبئة تبويب المعلومات الأساسية
        self.setup_edit_info_tab(tab_info, job)
        
        # تعبئة تبويب حالة الطلب
        self.setup_status_tab(tab_status, job)
        
        # تعبئة تبويب قطع الغيار
        self.setup_parts_tab(tab_parts, job)
        
        # تعبئة تبويب المدفوعات
        self.setup_payments_tab(tab_payments, job)
        
        # أزرار الحفظ والإلغاء
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=10)
        
        def save_changes():
            try:
                # جمع البيانات من حقول النموذج
                customer_name = customer_entry.get().strip()
                phone = phone_entry.get().strip()
                email = email_entry.get().strip()
                address = address_entry.get().strip()
                device_type = device_type_combo.get()
                model = model_entry.get().strip()
                serial = serial_entry.get().strip()
                issue = issue_text.get("1.0", tk.END).strip()
                notes = notes_text.get("1.0", tk.END).strip()
                
                # التحقق من البيانات المطلوبة
                if not customer_name or not phone:
                    messagebox.showwarning("تحذير", "الرجاء إدخال اسم العميل ورقم الهاتف")
                    return
                
                # تحديث بيانات العميل
                success, message = self.maintenance_service.update_customer(
                    customer_id=job['customer']['id'],
                    name=customer_name,
                    phone=phone,
                    email=email if email else None,
                    address=address if address else None
                )
                
                if not success:
                    messagebox.showerror("خطأ", f"فشل في تحديث بيانات العميل: {message}")
                    return
                
                # تحديث بيانات طلب الصيانة
                success, message = self.maintenance_service.update_maintenance_job(
                    job_id=job['id'],
                    device_type=device_type,
                    device_model=model if model else None,
                    serial_number=serial if serial else None,
                    issue_description=issue,
                    notes=notes if notes else None
                )
                
                if success:
                    messagebox.showinfo("نجاح", "تم حفظ التغييرات بنجاح")
                    dialog.destroy()
                    self.load_data()
                else:
                    messagebox.showerror("خطأ", f"فشل في تحديث بيانات الصيانة: {message}")
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
        
        ctk.CTkButton(
            btn_frame, 
            text="حفظ التغييرات", 
            command=save_changes
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="إغلاق", 
            command=dialog.destroy,
            fg_color="gray",
            hover_color="#616161"
        ).pack(side=tk.LEFT, padx=5)
    
    def setup_edit_info_tab(self, parent, job):
        """إعداد تبويب معلومات الطلب"""
        # حقول النموذج
        ctk.CTkLabel(parent, text="رقم التتبع:").grid(row=0, column=0, sticky=tk.W, pady=(10, 0))
        ctk.CTkLabel(parent, text=job['tracking_code'], font=("Arial", 12, "bold")).grid(row=0, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="تاريخ الاستلام:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        ctk.CTkLabel(parent, text=job['received_at']).grid(row=1, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="اسم العميل:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        customer_entry = ctk.CTkEntry(parent, width=300)
        customer_entry.insert(0, job['customer']['name'])
        customer_entry.grid(row=2, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="رقم الهاتف:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        phone_entry = ctk.CTkEntry(parent, width=200)
        phone_entry.insert(0, job['customer']['phone'])
        phone_entry.grid(row=3, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="البريد الإلكتروني:").grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        email_entry = ctk.CTkEntry(parent, width=300)
        email_entry.insert(0, job['customer'].get('email', ''))
        email_entry.grid(row=4, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="العنوان:").grid(row=5, column=0, sticky=tk.W, pady=(10, 0))
        address_entry = ctk.CTkEntry(parent, width=400)
        address_entry.insert(0, job['customer'].get('address', ''))
        address_entry.grid(row=5, column=1, sticky=tk.W, pady=(10, 0))
        
        # معلومات الجهاز
        ctk.CTkLabel(parent, text="معلومات الجهاز", font=("Arial", 12, "bold")).grid(row=6, column=0, columnspan=2, pady=(20, 10), sticky=tk.W)
        
        ctk.CTkLabel(parent, text="نوع الجهاز:").grid(row=7, column=0, sticky=tk.W, pady=(10, 0))
        device_type_combo = ctk.CTkComboBox(
            parent,
            values=["هاتف محمول", "حاسوب محمول", "حاسوب مكتبي", "تابلت", "أخرى"],
            width=200
        )
        device_type_combo.set(job['device_type'])
        device_type_combo.grid(row=7, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="الموديل:").grid(row=8, column=0, sticky=tk.W, pady=(10, 0))
        model_entry = ctk.CTkEntry(parent, width=200)
        model_entry.insert(0, job.get('device_model', ''))
        model_entry.grid(row=8, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="الرقم التسلسلي:").grid(row=9, column=0, sticky=tk.W, pady=(10, 0))
        serial_entry = ctk.CTkEntry(parent, width=200)
        serial_entry.insert(0, job.get('serial_number', ''))
        serial_entry.grid(row=9, column=1, sticky=tk.W, pady=(10, 0))
        
        # ربط التنقل بين الحقول في نافذة التعديل
        customer_entry.bind('<Return>', lambda e: phone_entry.focus())
        phone_entry.bind('<Return>', lambda e: email_entry.focus())
        email_entry.bind('<Return>', lambda e: address_entry.focus())
        address_entry.bind('<Return>', lambda e: device_type_combo.focus())
        device_type_combo.bind('<Return>', lambda e: model_entry.focus())
        model_entry.bind('<Return>', lambda e: serial_entry.focus())
        serial_entry.bind('<Return>', lambda e: issue_text.focus())
        
        ctk.CTkLabel(parent, text="وصف العطل:").grid(row=10, column=0, sticky=tk.NW, pady=(10, 0))
        issue_text = ctk.CTkTextbox(parent, width=400, height=100)
        issue_text.insert("1.0", job['issue_description'])
        issue_text.grid(row=10, column=1, sticky=tk.W, pady=(10, 0))
        
        ctk.CTkLabel(parent, text="ملاحظات:").grid(row=11, column=0, sticky=tk.NW, pady=(10, 0))
        notes_text = ctk.CTkTextbox(parent, width=400, height=80)
        notes_text.insert("1.0", job.get('notes', ''))
        notes_text.grid(row=11, column=1, sticky=tk.W, pady=(10, 0))
        
        # تكوين الأعمدة
        parent.columnconfigure(1, weight=1)
    
    def setup_status_tab(self, parent, job):
        """إعداد تبويب حالة الطلب"""
        # معلومات الحالة الحالية
        status_frame = ctk.CTkFrame(parent)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(status_frame, text="الحالة الحالية:", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        status_var = tk.StringVar(value=job['status'])
        statuses = [
            ("received", "تم الاستلام"),
            ("inspection", "قيد الفحص"),
            ("repair", "قيد الإصلاح"),
            ("ready", "جاهز للتسليم"),
            ("delivered", "تم التسليم"),
            ("cancelled", "ملغي")
        ]
        
        for status, label in statuses:
            rb = ctk.CTkRadioButton(
                status_frame,
                text=label,
                variable=status_var,
                value=status
            )
            rb.pack(anchor=tk.W, padx=20, pady=2)
        
        # حقل الملاحظات
        ctk.CTkLabel(parent, text="ملاحظات التحديث:").pack(anchor=tk.W, padx=5, pady=(10, 0))
        notes_text = ctk.CTkTextbox(parent, height=100)
        notes_text.pack(fill=tk.X, padx=5, pady=(0, 10))
        
        # زر تحديث الحالة
        def update_status():
            new_status = status_var.get()
            notes = notes_text.get("1.0", tk.END).strip()
            
            if not notes:
                messagebox.showwarning("تحذير", "الرجاء إدخال ملاحظات التحديث")
                return
            
            try:
                success, message = self.maintenance_service.update_job_status(
                    job_id=job['id'],
                    new_status=new_status,
                    notes=notes,
                    user_id=1  # سيتم استبداله بمعرف المستخدم الحالي
                )
                
                if success:
                    messagebox.showinfo("نجاح", message)
                    parent.winfo_toplevel().destroy()
                    self.load_data()
                else:
                    messagebox.showerror("خطأ", message)
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
        
        ctk.CTkButton(
            parent,
            text="تحديث الحالة",
            command=update_status
        ).pack(pady=10)
        
        # سجل تغييرات الحالة
        ctk.CTkLabel(parent, text="سجل التغييرات:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=5, pady=(20, 5))
        
        # إنشاء جدول سجل التغييرات
        columns = ("date", "status", "user", "notes")
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        # تكوين العناوين
        tree.heading("date", text="التاريخ")
        tree.heading("status", text="الحالة")
        tree.heading("user", text="المستخدم")
        tree.heading("notes", text="الملاحظات")
        
        # تكوين عرض الأعمدة
        tree.column("date", width=150, anchor=tk.CENTER)
        tree.column("status", width=120, anchor=tk.CENTER)
        tree.column("user", width=150, anchor=tk.CENTER)
        tree.column("notes", width=300, anchor=tk.W)
        
        # إضافة البيانات
        for history in job.get('status_history', []):
            tree.insert("", tk.END, values=(
                history['created_at'],
                history['status'],
                history['changed_by'],
                history.get('notes', '')
            ))
        
        # إضافة شريط التمرير
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        
        # تعبئة واجهة المستخدم
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_parts_tab(self, parent, job):
        """إعداد تبويب قطع الغيار"""
        # إطار إضافة قطعة غيار جديدة
        add_frame = ctk.CTkFrame(parent)
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(add_frame, text="إضافة قطعة غيار:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        # حقول إضافة قطعة غيار
        part_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        part_frame.pack(fill=tk.X, pady=5)
        
        ctk.CTkLabel(part_frame, text="القطعة:").grid(row=0, column=0, padx=5, pady=2)
        part_combo = ctk.CTkComboBox(part_frame, width=200)
        part_combo.grid(row=0, column=1, padx=5, pady=2)
        
        ctk.CTkLabel(part_frame, text="الكمية:").grid(row=0, column=2, padx=5, pady=2)
        qty_entry = ctk.CTkEntry(part_frame, width=80)
        qty_entry.insert(0, "1")
        qty_entry.grid(row=0, column=3, padx=5, pady=2)
        
        ctk.CTkLabel(part_frame, text="السعر:").grid(row=0, column=4, padx=5, pady=2)
        price_entry = ctk.CTkEntry(part_frame, width=100)
        price_entry.grid(row=0, column=5, padx=5, pady=2)
        
        # ربط التنقل بين حقول قطع الغيار
        part_combo.bind('<Return>', lambda e: qty_entry.focus())
        qty_entry.bind('<Return>', lambda e: price_entry.focus())
        price_entry.bind('<Return>', lambda e: add_part())
        
        def add_part():
            # تنفيذ إضافة قطعة غيار
            messagebox.showinfo("معلومة", "سيتم تنفيذ إضافة قطعة الغيار لاحقاً")
        
        ctk.CTkButton(
            part_frame,
            text="إضافة",
            command=add_part,
            width=80
        ).grid(row=0, column=6, padx=5, pady=2)
        
        # جدول قطع الغيار المستخدمة
        ctk.CTkLabel(parent, text="قطع الغيار المستخدمة:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=5, pady=(10, 5))
        
        columns = ("part", "qty", "price", "total")
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        # تكوين العناوين
        tree.heading("part", text="القطعة")
        tree.heading("qty", text="الكمية")
        tree.heading("price", text="السعر")
        tree.heading("total", text="الإجمالي")
        
        # تكوين عرض الأعمدة
        tree.column("part", width=250)
        tree.column("qty", width=80, anchor=tk.CENTER)
        tree.column("price", width=100, anchor=tk.E)
        tree.column("total", width=120, anchor=tk.E)
        
        # إضافة البيانات (سيتم استبدالها بالبيانات الفعلية)
        for part in job.get('parts', []):
            tree.insert("", tk.END, values=(
                part['name'],
                part['quantity'],
                f"{part['unit_price']:.2f}",
                f"{part['quantity'] * part['unit_price']:.2f}"
            ))
        
        # إضافة المجموع
        total = sum(p['quantity'] * p['unit_price'] for p in job.get('parts', []))
        tree.insert("", tk.END, values=(
            "",
            "",
            "الإجمالي:",
            f"{total:.2f}"
        ), tags=('total',))
        
        # تنسيق الصفوف
        tree.tag_configure('total', font=('Arial', 10, 'bold'))
        
        # إضافة شريط التمرير
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        
        # تعبئة واجهة المستخدم
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_payments_tab(self, parent, job):
        """إعداد تبويب المدفوعات"""
        # إطار إضافة دفعة جديدة
        add_frame = ctk.CTkFrame(parent)
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkLabel(add_frame, text="تسجيل دفعة جديدة:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        # حقول إضافة دفعة
        payment_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        payment_frame.pack(fill=tk.X, pady=5)
        
        ctk.CTkLabel(payment_frame, text="المبلغ:").grid(row=0, column=0, padx=5, pady=2)
        amount_entry = ctk.CTkEntry(payment_frame, width=150)
        amount_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ctk.CTkLabel(payment_frame, text="طريقة الدفع:").grid(row=0, column=2, padx=5, pady=2)
        method_combo = ctk.CTkComboBox(
            payment_frame,
            values=["نقداً", "تحويل بنكي", "بطاقة ائتمان", "أخرى"],
            width=150
        )
        method_combo.grid(row=0, column=3, padx=5, pady=2)
        
        ctk.CTkLabel(payment_frame, text="الملاحظات:").grid(row=0, column=4, padx=5, pady=2)
        notes_entry = ctk.CTkEntry(payment_frame, width=200)
        notes_entry.grid(row=0, column=5, padx=5, pady=2)
        
        # ربط التنقل بين حقول المدفوعات
        amount_entry.bind('<Return>', lambda e: method_combo.focus())
        method_combo.bind('<Return>', lambda e: notes_entry.focus())
        notes_entry.bind('<Return>', lambda e: add_payment())
        
        def add_payment():
            # تنفيذ إضافة دفعة
            messagebox.showinfo("معلومة", "سيتم تنفيذ إضافة الدفعة لاحقاً")
        
        ctk.CTkButton(
            payment_frame,
            text="تسجيل الدفعة",
            command=add_payment,
            width=120
        ).grid(row=0, column=6, padx=5, pady=2)
        
        # ملخص المدفوعات
        summary_frame = ctk.CTkFrame(parent)
        summary_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # حساب الإحصائيات
        total_cost = job.get('final_cost', job.get('estimated_cost', 0)) or 0
        total_paid = sum(p['amount'] for p in job.get('payments', []) if p['status'] != 'cancelled')
        remaining = max(0, total_cost - total_paid)
        
        # عرض الإحصائيات
        stats = [
            ("إجمالي التكلفة:", f"{total_cost:.2f} ر.س"),
            ("المدفوع:", f"{total_paid:.2f} ر.س"),
            ("المتبقي:", f"{remaining:.2f} ر.س")
        ]
        
        for i, (label, value) in enumerate(stats):
            ctk.CTkLabel(summary_frame, text=label, font=("Arial", 12, "bold")).grid(row=0, column=i*2, padx=10, pady=5, sticky=tk.E)
            ctk.CTkLabel(summary_frame, text=value, font=("Arial", 12)).grid(row=0, column=i*2+1, padx=(0, 20), pady=5, sticky=tk.W)
        
        # جدول المدفوعات
        ctk.CTkLabel(parent, text="سجل المدفوعات:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=5, pady=(10, 5))
        
        columns = ("date", "amount", "method", "status", "notes")
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        # تكوين العناوين
        tree.heading("date", text="التاريخ")
        tree.heading("amount", text="المبلغ")
        tree.heading("method", text="طريقة الدفع")
        tree.heading("status", text="الحالة")
        tree.heading("notes", text="الملاحظات")
        
        # تكوين عرض الأعمدة
        tree.column("date", width=150, anchor=tk.CENTER)
        tree.column("amount", width=100, anchor=tk.E)
        tree.column("method", width=120, anchor=tk.CENTER)
        tree.column("status", width=100, anchor=tk.CENTER)
        
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
        
        # ربط الأحداث
        def on_enter(event, next_widget=None):
            if next_widget:
                next_widget.focus_set()
            else:
                save()
            return "break"
        
        barcode_entry.bind('<Return>', lambda e: on_enter(e, customer_entry))
        customer_entry.bind('<Return>', lambda e: on_enter(e, phone_entry) if not search_customer() else None)
        phone_entry.bind('<Return>', lambda e: on_enter(e, device_type_entry))
        device_type_entry.bind('<Return>', lambda e: on_enter(e, issue_text))
        issue_text.bind('<Return>', on_enter)
        
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
                    ))
                
                # تحديث العداد
                self.status_count.configure(text=f"{len(jobs)} نتيجة بحث")
                
            else:
                messagebox.showerror("خطأ", f"فشل في البحث: {message}")
                
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
    
    def on_item_double_click(self, event):
        """معالجة حدث النقر المزدوج على عنصر في الجدول"""
        self.edit_maintenance()
    
    def generate_orders_report(self):
        """إنشاء تقرير بالطلبات"""
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, "تقرير طلبات الصيانة\n")
        self.report_text.insert(tk.END, "=" * 50 + "\n\n")
        
        # جلب بيانات الطلبات
        success, message, jobs = self.maintenance_service.search_jobs()
        
        if success:
            for job in jobs:
                self.report_text.insert(tk.END, f"رقم الطلب: {job['tracking_code']}\n")
                self.report_text.insert(tk.END, f"العميل: {job['customer_name']}\n")
                self.report_text.insert(tk.END, f"الجهاز: {job['device_type']} - {job.get('device_model', '')}\n")
                self.report_text.insert(tk.END, f"الحالة: {job['status']}\n")
                self.report_text.insert(tk.END, f"تاريخ الاستلام: {job['received_at'].strftime('%Y-%m-%d') if job['received_at'] else ''}\n")
                self.report_text.insert(tk.END, "-" * 50 + "\n\n")
            
            self.status_label.configure(text=f"تم إنشاء التقرير - {len(jobs)} طلب")
        else:
            messagebox.showerror("خطأ", f"فشل في إنشاء التقرير: {message}")
    
    def generate_payments_report(self):
        """إنشاء تقرير بالمدفوعات"""
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, "تقرير المدفوعات\n")
        self.report_text.insert(tk.END, "=" * 50 + "\n\n")
        
        # جلب بيانات الطلبات مع المدفوعات
        success, message, jobs = self.maintenance_service.search_jobs()
        
        if success:
            total_payments = 0
            
            for job in jobs:
                payments = job.get('payments', [])
                if not payments:
                    continue
                
                self.report_text.insert(tk.END, f"رقم الطلب: {job['tracking_code']}\n")
                self.report_text.insert(tk.END, f"العميل: {job['customer_name']}\n")
                
                for payment in payments:
                    if payment['status'] != 'cancelled':
                        self.report_text.insert(tk.END, f"- {payment['created_at']}: {payment['amount']:.2f} ر.س ({payment['payment_method']}) - {payment['status']}\n")
                        total_payments += payment['amount']
                
                self.report_text.insert(tk.END, "-" * 50 + "\n\n")
            
            self.report_text.insert(tk.END, f"\nإجمالي المدفوعات: {total_payments:.2f} ر.س\n")
            self.status_label.configure(text=f"تم إنشاء التقرير - إجمالي المدفوعات: {total_payments:.2f} ر.س")
        else:
            messagebox.showerror("خطأ", f"فشل في إنشاء التقرير: {message}")
