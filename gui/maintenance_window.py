"""
واجهة المستخدم الرئيسية لنظام إدارة الصيانة
"""

import os
import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import customtkinter as ctk
from datetime import datetime, timedelta
import qrcode
from PIL import Image, ImageTk
import io
import threading
import webbrowser
import urllib.parse
import json
from typing import List, Dict, Any
from services.maintenance_service import MaintenanceService
from services.code_service import CodeService
from database.connection import get_db
from utils.barcode_generator import BarcodeGenerator
from utils.notification_service import NotificationService
from utils.vcard_generator import VCardGenerator
from config import REPORTS_FOLDER, UPLOAD_FOLDER, TEMP_FOLDER, WHATSAPP_RECEIVED_MESSAGE, WHATSAPP_REPAIRED_MESSAGE, WHATSAPP_DELIVERED_MESSAGE
import config
from database.models import MaintenanceJob, Customer

class MaintenanceFrame(ctk.CTkFrame):
    """إطار إدارة طلبات الصيانة"""
    
    def __init__(self, parent, current_user=None):
        super().__init__(parent)
        self.parent = parent
        self.current_user = current_user
        
        # الحصول على اتصال قاعدة البيانات
        self.db = next(get_db())
        
        # الحصول على مسار قاعدة البيانات من الإعدادات
        from config import DATABASE_URL
        db_path = DATABASE_URL.replace('sqlite:///', '')
        
        self.code_service = CodeService(db_path)
        self.maintenance_service = MaintenanceService(self.db)
        self.barcode_generator = BarcodeGenerator()
        self.notification_service = NotificationService({})  # سيتم تحميل الإعدادات من ملف التكوين
        self.vcard_generator = VCardGenerator()  # مولد جهات الاتصال
        
        # خدمة التذكيرات الأسبوعية للديون
        from services.debt_reminder_service import DebtReminderService
        self.debt_reminder_service = DebtReminderService(self.maintenance_service)
        # بدء خدمة التذكيرات في الخلفية
        # self.debt_reminder_service.start()  # يمكن تفعيله عند الحاجة
        
        # إعداد التحديث التلقائي (مفعّل افتراضياً - محسّن للأداء)
        self.auto_refresh_enabled = True
        self.auto_refresh_interval = 30000  # 30 ثانية (تقليل التحديثات لتحسين الأداء)
        self.auto_refresh_job = None
        self.last_refresh_time = None
        self._last_load_time = None  # تتبع آخر وقت تحميل
        self._is_loading = False  # منع التحميل المتزامن
        
        # متغير لتتبع حالة الفلترة
        self.current_filter_status = None
        self._filter_mode_active = False  # تتبع حالة وضع الفلترة
        
        # Cache بسيط للبيانات (محسّن للأداء)
        self._stats_cache = None
        self._stats_cache_time = None
        self._cache_ttl = 30  # 30 ثانية (زيادة cache لتقليل الاستعلامات)
        self._last_stats_refresh = None  # تتبع آخر تحديث للإحصائيات
        self._data_cache = None  # Cache للبيانات
        self._data_cache_time = None
        self._data_cache_key = None
        self._data_cache_ttl = 10  # 10 ثواني cache للبيانات
        
        # إعدادات الأداء
        self.monthly_stats_enabled = getattr(config, "ENABLE_MONTHLY_STATS", True)
        
        # إعداد واجهة المستخدم
        self.debt_summary_data = {
            "total_unpaid": 0.0,
            "unpaid_count": 0,
            "total_paid": 0.0
        }
        self.debts_data_unpaid = []
        self.debts_data_paid = []
        self.current_debt_filter = "unpaid"
        self.debts_access_granted = False
        self.debts_password = "a1s2h3r4f5"
        self.debts_access_granted = False
        self.reports_access_granted = False  # قفل صفحة التقارير
        self.last_active_tab = "إحصائيات"
        self._tab_change_guard = False
        self.debts_locked_notice = None
        self.reports_locked_notice = None  # رسالة قفل التقارير

        self.setup_ui()
        
        # إعداد التنقل بالـ Enter للواجهة الرئيسية
        self.setup_enter_navigation(self)
        
        # بدء التحديث التلقائي
        self.start_auto_refresh()
        
        # تحديث الإحصائيات مرة واحدة عند التحميل (بعد إنشاء البطاقات)
        # سيتم استدعاؤها من setup_stats_tab بعد إنشاء stats_cards
    
    def destroy(self):
        """تنظيف الموارد عند إغلاق الإطار"""
        # إيقاف التحديث التلقائي
        self.stop_auto_refresh()
        # استدعاء destroy للكلاس الأب
        super().destroy()
    
    def setup_enter_navigation(self, parent_widget):
        """إعداد التنقل بالـ Enter لجميع حقول الإدخال في النافذة"""
        def find_all_inputs(widget, inputs_list):
            """البحث عن جميع حقول الإدخال في النافذة"""
            try:
                # إضافة حقول الإدخال إلى القائمة
                if isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox)):
                    inputs_list.append(widget)
                elif isinstance(widget, ctk.CTkComboBox):
                    inputs_list.append(widget)
                
                # البحث في العناصر الفرعية
                for child in widget.winfo_children():
                    find_all_inputs(child, inputs_list)
            except:
                pass
        
        inputs = []
        find_all_inputs(parent_widget, inputs)
        
        # ربط Enter للانتقال بين الحقول
        for i, input_widget in enumerate(inputs):
            def make_navigate_handler(current_idx):
                def navigate_on_enter(event):
                    # الانتقال للحقل التالي
                    next_idx = (current_idx + 1) % len(inputs)
                    next_widget = inputs[next_idx]
                    
                    # دالة التمرير المدمجة - بسيطة ومباشرة
                    def do_scroll():
                        """تمرير مدمج مع الانتقال - بسيط جداً"""
                        try:
                            widget = next_widget
                            widget.update_idletasks()
                            
                            # البحث عن scrollable frame
                            current = widget
                            scrollable_frame = None
                            while current:
                                try:
                                    if isinstance(current, ctk.CTkScrollableFrame):
                                        scrollable_frame = current
                                        break
                                    current = current.master
                                except:
                                    break
                            
                            if scrollable_frame:
                                scrollable_frame.update_idletasks()
                                
                                # محاولة الحصول على Canvas بكل الطرق الممكنة
                                canvas = None
                                scrollbar = None
                                
                                # الطريقة 1 - _parent_canvas
                                try:
                                    canvas = scrollable_frame._parent_canvas
                                    if canvas:
                                        canvas.yview_scroll(96, "units")
                                        canvas.update_idletasks()
                                        return
                                except Exception as e1:
                                    pass
                                
                                # الطريقة 2 - _canvas
                                try:
                                    canvas = scrollable_frame._canvas
                                    if canvas:
                                        canvas.yview_scroll(96, "units")
                                        canvas.update_idletasks()
                                        return
                                except Exception as e2:
                                    pass
                                
                                # الطريقة 3 - البحث في children
                                try:
                                    for child in scrollable_frame.winfo_children():
                                        if isinstance(child, tk.Canvas):
                                            child.yview_scroll(96, "units")
                                            child.update_idletasks()
                                            return
                                except Exception as e3:
                                    pass
                                
                                # الطريقة 4 - استخدام _scrollbar
                                try:
                                    scrollbar = scrollable_frame._scrollbar
                                    if scrollbar and hasattr(scrollbar, 'set'):
                                        # استخدام scrollbar مباشرة
                                        v1, v2 = scrollbar.get()
                                        new_v1 = min(1.0, v1 + 0.05)
                                        scrollbar.set(new_v1, v2)
                                        print("✅ التمرير نجح بالطريقة 4")
                                        return
                                except Exception as e4:
                                    pass
                                
                                # الطريقة 5 - استخدام scroll_canvas
                                try:
                                    if hasattr(scrollable_frame, 'scroll_canvas'):
                                        scrollable_frame.scroll_canvas.yview_scroll(96, "units")
                                        return
                                except Exception as e5:
                                    pass
                                
                        except Exception as e:
                            print(f"❌ خطأ في do_scroll: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    # إذا كان الحقل التالي هو Textbox، ننتقل له
                    if isinstance(next_widget, ctk.CTkTextbox):
                        next_widget.focus()
                        # وضع المؤشر في البداية
                        try:
                            next_widget.mark_set(tk.INSERT, "1.0")
                        except:
                            pass
                    else:
                        next_widget.focus()
                    
                    # التمرير مباشرة بعد الانتقال - محاولة واحدة بسرعة
                    parent_widget.after(50, do_scroll)
                    
                    return "break"  # منع معالجة الحدث بشكل افتراضي
                return navigate_on_enter
            
            # ربط Enter للانتقال
            input_widget.bind('<Return>', make_navigate_handler(i))
            input_widget.bind('<KP_Enter>', make_navigate_handler(i))  # Enter من لوحة المفاتيح الرقمية
        
        # إضافة دعم للجداول (Treeview) - Enter للانتقال للصف التالي
        def find_all_trees(widget, trees_list):
            """البحث عن جميع الجداول في النافذة"""
            try:
                if isinstance(widget, ttk.Treeview):
                    trees_list.append(widget)
                for child in widget.winfo_children():
                    find_all_trees(child, trees_list)
            except:
                pass
        
        trees = []
        find_all_trees(parent_widget, trees)
        
        # ربط Enter للجداول
        for tree in trees:
            def make_tree_navigate_handler(tree_widget):
                def navigate_tree_on_enter(event):
                    # الحصول على الصف المحدد حالياً
                    selection = tree_widget.selection()
                    if selection:
                        current_item = selection[0]
                        # الحصول على الصف التالي
                        next_item = tree_widget.next(current_item)
                        if not next_item:
                            # إذا لم يكن هناك صف تالي، ننتقل للأول
                            children = tree_widget.get_children()
                            if children:
                                next_item = children[0]
                        
                        if next_item:
                            tree_widget.selection_set(next_item)
                            tree_widget.focus(next_item)
                            # التمرير للصف المحدد
                            tree_widget.see(next_item)
                    else:
                        # إذا لم يكن هناك صف محدد، نحدد الأول
                        children = tree_widget.get_children()
                        if children:
                            first_item = children[0]
                            tree_widget.selection_set(first_item)
                            tree_widget.focus(first_item)
                            tree_widget.see(first_item)
                    
                    return "break"
                return navigate_tree_on_enter
            
            tree.bind('<Return>', make_tree_navigate_handler(tree))
            tree.bind('<KP_Enter>', make_tree_navigate_handler(tree))
    
    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        # تكوين الشبكة
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # شريط الأدوات - صفين
        toolbar_container = ctk.CTkFrame(self, fg_color=("gray90", "gray16"))
        toolbar_container.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        
        # الصف الأول: الأزرار الأساسية + البحث
        toolbar_row1 = ctk.CTkFrame(toolbar_container, fg_color="transparent")
        toolbar_row1.pack(fill=tk.X, pady=(5, 2))
        
        # الأزرار الأساسية على اليمين
        btn_add = ctk.CTkButton(toolbar_row1, text="➕ إضافة", command=self.add_maintenance, width=100)
        btn_add.pack(side=tk.RIGHT, padx=3)
        
        # زر حذف ذكي (يحذف المحدد إذا وجد، وإلا يحذف الصف الحالي)
        btn_delete = ctk.CTkButton(toolbar_row1, text="🗑️ حذف", command=self.smart_delete, 
                                    width=80, fg_color="#d32f2f", hover_color="#b71c1c")
        btn_delete.pack(side=tk.RIGHT, padx=3)
        
        # حقل البحث على اليسار
        self.search_var = tk.StringVar()
        
        search_frame = ctk.CTkFrame(toolbar_row1, fg_color="transparent")
        search_frame.pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(search_frame, text="🔍", font=("Arial", 16)).pack(side=tk.LEFT, padx=(0, 3))
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, width=280, 
                                     placeholder_text="ابحث برقم العميل، اسم العميل، نوع الجهاز...")
        search_entry.pack(side=tk.LEFT, padx=2)
        search_entry.bind('<Return>', lambda e: self.search_maintenance())
        search_entry.bind('<KeyPress-Return>', lambda e: self.search_maintenance())
        
        btn_search = ctk.CTkButton(search_frame, text="بحث", command=self.search_maintenance, 
                                    width=70, fg_color="#4CAF50", hover_color="#45a049")
        btn_search.pack(side=tk.LEFT, padx=2)
        
        btn_clear_search = ctk.CTkButton(search_frame, text="✖", command=self.clear_search, 
                                         width=35, fg_color="#757575", hover_color="#616161")
        btn_clear_search.pack(side=tk.LEFT, padx=2)
        
        # الصف الثاني: الأزرار الثانوية
        toolbar_row2 = ctk.CTkFrame(toolbar_container, fg_color="transparent")
        toolbar_row2.pack(fill=tk.X, pady=(2, 5))
        
        # أزرار الإعدادات والنسخ الاحتياطي
        btn_currency = ctk.CTkButton(toolbar_row2, text="💰 العملة", command=self.show_currency_settings, 
                                      width=90, fg_color="#FF9800", hover_color="#F57C00")
        btn_currency.pack(side=tk.LEFT, padx=3)
        
        btn_backup = ctk.CTkButton(toolbar_row2, text="💾 نسخ احتياطي", command=self.show_backup_window, 
                                    width=110, fg_color="#9C27B0", hover_color="#7B1FA2")
        btn_backup.pack(side=tk.LEFT, padx=3)
        
        # زر حفظ جهة اتصال
        btn_save_contact = ctk.CTkButton(toolbar_row2, text="📱 حفظ عميل", command=self.show_save_contact_dialog, 
                                          width=100, fg_color="#9C27B0", hover_color="#7B1FA2")
        btn_save_contact.pack(side=tk.LEFT, padx=3)
        
        # زر حسابات العملاء المميزين
        btn_vip_accounts = ctk.CTkButton(toolbar_row2, text="⭐ حسابات مميزة", command=self.show_vip_accounts, 
                                         width=120, fg_color="#ff9800", hover_color="#f57c00")
        btn_vip_accounts.pack(side=tk.LEFT, padx=3)
        
        # زر إدارة رسائل الواتساب الجماعية
        btn_whatsapp_broadcast = ctk.CTkButton(toolbar_row2, text="📢 رسائل جماعية", command=self.show_whatsapp_broadcast_settings, 
                                               width=120, fg_color="#25D366", hover_color="#128C7E")
        btn_whatsapp_broadcast.pack(side=tk.LEFT, padx=3)
        
        # زر التذكيرات الأسبوعية
        self.reminders_enabled = False
        self.btn_reminders = ctk.CTkButton(
            toolbar_row2, 
            text="📅 تذكيرات أسبوعية", 
            command=self.toggle_weekly_reminders, 
            width=130, 
            fg_color="#607d8b", 
            hover_color="#455a64"
        )
        self.btn_reminders.pack(side=tk.LEFT, padx=3)
        
        # ملاحظة توضيحية على اليمين
        ctk.CTkLabel(toolbar_row2, text="💡 اضغط على ☐ في رأس الجدول لتحديد/إلغاء الكل", 
                     font=("Arial", 10), text_color="#666666").pack(side=tk.RIGHT, padx=10)
        
        # إنشاء المحتوى الرئيسي
        self.create_main_content()
        
        # إنشاء شريط الحالة
        self.create_status_bar()
    
    def create_main_content(self):
        """إنشاء منطقة المحتوى الرئيسي"""
        # إنشاء إطار رئيسي للمحتوى
        content_frame = ctk.CTkFrame(self)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)
        
        # إنشاء علامات التبويب
        self.tabview = ctk.CTkTabview(content_frame)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=5, pady=2)
        
        # إضافة علامات التبويب
        self.tabview.add("إحصائيات")
        self.tabview.add("الديون")
        self.tabview.add("التقارير")
        
        # إنشاء قائمة الطلبات مباشرة (بدون تبويب)
        self.setup_main_treeview(content_frame)
        
        # تكوين علامة التبويب الأولى (الإحصائيات)
        self.setup_stats_tab()
        
        # تكوين علامة التبويب الثانية (الديون)
        self.setup_debts_tab()
        
        # تكوين علامة التبويب الثالثة (التقارير)
        self.setup_reports_tab()
        
        # تهيئة التحكم في التبويبات
        self.tabview.set(self.last_active_tab)
        self.tabview.configure(command=self.on_main_tab_changed)
        self.update_debts_locked_state()
        self.update_reports_locked_state()
        
        # تحميل البيانات بعد إنشاء الواجهة
        self.load_data()

    def on_main_tab_changed(self, event=None):
        """معالجة تغيير علامة التبويب الرئيسية"""
        if not hasattr(self, "tabview"):
            return
        if self._tab_change_guard:
            return

        selected_tab = self.tabview.get()

        if selected_tab == "الديون" and not self.debts_access_granted:
            # إظهار حالة القفل الحالية
            self.update_debts_locked_state()

            # مطالبة المستخدم بكلمة المرور
            unlocked = self.prompt_debts_access()
            if not unlocked:
                # إعادة التبويب إلى آخر حالة معروفة
                self._tab_change_guard = True
                try:
                    self.tabview.set(self.last_active_tab)
                finally:
                    self._tab_change_guard = False
                return
            # تم إلغاء قفل تبويب الديون، حدث البيانات
            self.load_debts_data()

        if selected_tab == "التقارير" and not self.reports_access_granted:
            # إظهار حالة القفل الحالية
            self.update_reports_locked_state()

            # مطالبة المستخدم بكلمة المرور
            unlocked = self.prompt_reports_access()
            if not unlocked:
                # إعادة التبويب إلى آخر حالة معروفة
                self._tab_change_guard = True
                try:
                    self.tabview.set(self.last_active_tab)
                finally:
                    self._tab_change_guard = False
                return

        self.last_active_tab = selected_tab
        self.update_debts_locked_state()
        self.update_reports_locked_state()

    def prompt_debts_access(self) -> bool:
        """طلب كلمة المرور لتبويب الديون"""
        if self.debts_access_granted:
            return True

        password = simpledialog.askstring(
            "🔒 حماية الديون",
            "يرجى إدخال كلمة المرور للوصول إلى تبويب الديون:",
            show="*",
            parent=self
        )

        if password is None:
            # المستخدم ألغى الإدخال
            return False

        if password.strip() != self.debts_password:
            messagebox.showerror("خطأ", "كلمة المرور غير صحيحة.")
            return False

        self.debts_access_granted = True
        self.update_debts_locked_state()
        messagebox.showinfo("نجاح", "تم فتح تبويب الديون بنجاح.")
        return True
    
    def prompt_reports_access(self) -> bool:
        """طلب كلمة المرور لتبويب التقارير"""
        if self.reports_access_granted:
            return True

        password = simpledialog.askstring(
            "🔒 حماية التقارير",
            "يرجى إدخال كلمة المرور للوصول إلى تبويب التقارير:",
            show="*",
            parent=self
        )

        if password is None:
            # المستخدم ألغى الإدخال
            return False

        if password.strip() != self.debts_password:  # نفس كلمة المرور للديون
            messagebox.showerror("خطأ", "كلمة المرور غير صحيحة.")
            return False

        self.reports_access_granted = True
        self.update_reports_locked_state()
        messagebox.showinfo("نجاح", "تم فتح تبويب التقارير بنجاح.")
        return True

    def update_debts_locked_state(self):
        """تحديث واجهة تبويب الديون بناءً على حالة القفل"""
        if not hasattr(self, "tabview"):
            return

        try:
            tab = self.tabview.tab("الديون")
        except KeyError:
            return

        locked = not self.debts_access_granted

        if locked:
            if self.debts_locked_notice is None:
                overlay = ctk.CTkFrame(tab, fg_color="#fdecea", corner_radius=12)
                overlay.place(relx=0.5, rely=0.5, anchor=tk.CENTER, relwidth=0.9, relheight=0.8)

                ctk.CTkLabel(
                    overlay,
                    text="🔒 تبويب الديون محمي بكلمة مرور",
                    font=("Arial", 18, "bold"),
                    text_color="#c62828",
                    justify=tk.CENTER
                ).pack(pady=(30, 10), padx=30)

                ctk.CTkLabel(
                    overlay,
                    text="اضغط على الزر أدناه لإدخال كلمة المرور ومتابعة العرض.",
                    font=("Arial", 13),
                    text_color="#7f0000",
                    wraplength=500,
                    justify=tk.CENTER
                ).pack(pady=(0, 20), padx=30)

                ctk.CTkButton(
                    overlay,
                    text="🔓 إدخال كلمة المرور",
                    fg_color="#c62828",
                    hover_color="#ad2424",
                    command=self.prompt_debts_access,
                    width=240
                ).pack(pady=10)

                overlay.lift()
                self.debts_locked_notice = overlay
            else:
                self.debts_locked_notice.lift()
        else:
            if self.debts_locked_notice is not None:
                self.debts_locked_notice.place_forget()
                self.debts_locked_notice.destroy()
                self.debts_locked_notice = None
    
    def update_reports_locked_state(self):
        """تحديث واجهة تبويب التقارير بناءً على حالة القفل"""
        if not hasattr(self, "tabview"):
            return

        try:
            tab = self.tabview.tab("التقارير")
        except KeyError:
            return

        locked = not self.reports_access_granted

        if locked:
            if self.reports_locked_notice is None:
                overlay = ctk.CTkFrame(tab, fg_color="#fdecea", corner_radius=12)
                overlay.place(relx=0.5, rely=0.5, anchor=tk.CENTER, relwidth=0.9, relheight=0.8)

                ctk.CTkLabel(
                    overlay,
                    text="🔒 تبويب التقارير محمي بكلمة مرور",
                    font=("Arial", 18, "bold"),
                    text_color="#c62828",
                    justify=tk.CENTER
                ).pack(pady=(30, 10), padx=30)

                ctk.CTkLabel(
                    overlay,
                    text="اضغط على الزر أدناه لإدخال كلمة المرور ومتابعة العرض.",
                    font=("Arial", 13),
                    text_color="#7f0000",
                    wraplength=500,
                    justify=tk.CENTER
                ).pack(pady=(0, 20), padx=30)

                ctk.CTkButton(
                    overlay,
                    text="🔓 إدخال كلمة المرور",
                    fg_color="#c62828",
                    hover_color="#ad2424",
                    command=self.prompt_reports_access,
                    width=240
                ).pack(pady=10)

                overlay.lift()
                self.reports_locked_notice = overlay
            else:
                self.reports_locked_notice.lift()
        else:
            if self.reports_locked_notice is not None:
                self.reports_locked_notice.place_forget()
                self.reports_locked_notice.destroy()
                self.reports_locked_notice = None
    
    def setup_main_treeview(self, parent):
        """إعداد قائمة الطلبات الرئيسية"""
        # إنشاء Treeview في الإطار الرئيسي
        tree_frame = ctk.CTkFrame(parent)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=2)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
        # إنشاء Treeview لعرض الطلبات
        columns = ("select", "id", "tracking_code", "customer_name", "customer_phone", "device_type", "serial_number", "status", "price", "payment", "received_date", "delivered_date")
        self.tree = ttk.Treeview(
            tree_frame, 
            columns=columns, 
            show="headings",
            selectmode="extended",  # للسماح بتحديد متعدد
            height=20  # تقليل الارتفاع
        )
        
        # تحسين الخط في القائمة
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 9))
        style.configure("Treeview.Heading", font=("Arial", 9, "bold"))
        
        # تكوين العناوين
        # متغير لتتبع حالة التحديد الكلي
        self.all_selected = False
        
        # رأس عمود التحديد مع إمكانية النقر عليه
        self.tree.heading("select", text="☐", command=self.toggle_select_all)
        self.tree.heading("id", text="#")
        self.tree.heading("tracking_code", text="رقم التتبع")
        self.tree.heading("customer_name", text="اسم العميل")
        self.tree.heading("customer_phone", text="رقم العميل")
        self.tree.heading("device_type", text="نوع الجهاز")
        self.tree.heading("serial_number", text="الرقم التسلسلي")
        self.tree.heading("status", text="الحالة")
        self.tree.heading("price", text="السعر")
        self.tree.heading("payment", text="الدفع")
        self.tree.heading("received_date", text="تاريخ الاستلام")
        self.tree.heading("delivered_date", text="تاريخ التسليم")
        
        # تكوين عرض الأعمدة - تصميم مضغوط
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("select", width=40, anchor=tk.CENTER)
        self.tree.column("id", width=40, anchor=tk.CENTER)
        self.tree.column("tracking_code", width=100, anchor=tk.CENTER)
        self.tree.column("customer_name", width=120, anchor=tk.CENTER)
        self.tree.column("customer_phone", width=90, anchor=tk.CENTER)
        self.tree.column("device_type", width=100, anchor=tk.CENTER)
        self.tree.column("serial_number", width=120, anchor=tk.CENTER)
        self.tree.column("status", width=90, anchor=tk.CENTER)
        self.tree.column("price", width=80, anchor=tk.CENTER)
        self.tree.column("payment", width=80, anchor=tk.CENTER)
        self.tree.column("received_date", width=90, anchor=tk.CENTER)
        self.tree.column("delivered_date", width=90, anchor=tk.CENTER)
        
        # إضافة شريط التمرير
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        # تعبئة واجهة المستخدم
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # ربط أحداث النقر
        self.tree.bind("<Double-1>", self.on_item_double_click)
        self.tree.bind("<Button-1>", self.on_item_click)
    
    def setup_stats_tab(self):
        """إعداد علامة تبويب الإحصائيات"""
        if hasattr(self, 'tabview'):
            tab = self.tabview.tab("إحصائيات")
        else:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        
        # إضافة عناصر واجهة المستخدم للإحصائيات
        stats_frame = ctk.CTkFrame(tab)
        stats_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=2)
        
        # إضافة بطاقات الإحصائيات
        self.stats_cards = {}
        stats = [
            ("إجمالي الطلبات", "0", "#2196F3"),
            ("قيد المعالجة", "0", "#FFC107"),
            ("جاهزة للتسليم", "0", "#4CAF50"),
            ("تم التسليم", "0", "#9C27B0")
        ]
        
        for i, (title, value, color) in enumerate(stats):
            card = ctk.CTkFrame(stats_frame, fg_color=color, corner_radius=10, cursor="hand2")
            card.grid(row=0, column=i, padx=10, pady=2, sticky="nsew")
            
            # تحديد حالة الفلترة لكل بطاقة
            filter_status = None
            if title == "إجمالي الطلبات":
                filter_status = None  # لا فلترة
            elif title == "قيد المعالجة":
                filter_status = "received"
            elif title == "جاهزة للتسليم":
                filter_status = "repaired"
            elif title == "تم التسليم":
                filter_status = "delivered"
            
            # إضافة حدث النقر
            card.bind("<Button-1>", lambda e, status=filter_status: self.filter_by_status_from_stats(status))
            
            value_label = ctk.CTkLabel(
                card, 
                text=value, 
                font=("Arial", 24, "bold"),
                text_color="white",
                cursor="hand2"
            )
            value_label.pack(padx=20, pady=(15, 5))
            value_label.bind("<Button-1>", lambda e, status=filter_status: self.filter_by_status_from_stats(status))
            
            title_label = ctk.CTkLabel(
                card, 
                text=title,
                text_color="white",
                cursor="hand2"
            )
            title_label.pack(padx=20, pady=(0, 1))
            title_label.bind("<Button-1>", lambda e, status=filter_status: self.filter_by_status_from_stats(status))
            
            self.stats_cards[title] = card
        
        # تحديث الإحصائيات بعد إنشاء البطاقات
        # استخدام after للتأكد من أن البطاقات جاهزة تماماً
        self.after(50, lambda: self.update_stats(force_refresh=True))
        
        # إخفاء قسم الإحصائيات الشهرية إذا تم تعطيله
        if self.monthly_stats_enabled:
            chart_frame = ctk.CTkFrame(tab)
            chart_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=2)
            
            ctk.CTkLabel(
                chart_frame,
                text="إحصائيات الطلبات حسب الشهر",
                font=("Arial", 14, "bold")
            ).pack(pady=2)
    
    def setup_debts_tab(self):
        """إعداد تبويب الديون"""
        if hasattr(self, 'tabview'):
            tab = self.tabview.tab("الديون")
        else:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # إطار الملخص
        summary_frame = ctk.CTkFrame(tab, fg_color="#ffebee", corner_radius=10)
        summary_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=2)
        summary_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # بطاقات الملخص
        self.debt_cards = {}
        
        # إجمالي الديون
        debt_card = ctk.CTkFrame(summary_frame, fg_color="#f44336", corner_radius=8)
        debt_card.grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        ctk.CTkLabel(debt_card, text="💰 إجمالي الديون", font=("Arial", 12, "bold"), text_color="white").pack(pady=(5, 3))
        self.total_debt_label = ctk.CTkLabel(debt_card, text="0 $", font=("Arial", 18, "bold"), text_color="white")
        self.total_debt_label.pack(pady=(0, 1))
        debt_card.bind("<Button-1>", lambda _event, key="total_unpaid": self.show_debt_summary_detail(key))
        self.total_debt_label.bind("<Button-1>", lambda _event, key="total_unpaid": self.show_debt_summary_detail(key))
        
        # عدد المدينين
        count_card = ctk.CTkFrame(summary_frame, fg_color="#ff9800", corner_radius=8)
        count_card.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        ctk.CTkLabel(count_card, text="👥 عدد المدينين", font=("Arial", 12, "bold"), text_color="white").pack(pady=(5, 3))
        self.debtors_count_label = ctk.CTkLabel(count_card, text="0", font=("Arial", 18, "bold"), text_color="white")
        self.debtors_count_label.pack(pady=(0, 1))
        count_card.bind("<Button-1>", lambda _event, key="unpaid_count": self.show_debt_summary_detail(key))
        self.debtors_count_label.bind("<Button-1>", lambda _event, key="unpaid_count": self.show_debt_summary_detail(key))
        
        # إجمالي المدفوعات
        paid_card = ctk.CTkFrame(summary_frame, fg_color="#4caf50", corner_radius=8)
        paid_card.grid(row=0, column=2, padx=5, pady=2, sticky="ew")
        ctk.CTkLabel(paid_card, text="✅ إجمالي المدفوعات", font=("Arial", 12, "bold"), text_color="white").pack(pady=(5, 3))
        self.total_paid_label = ctk.CTkLabel(paid_card, text="0 $", font=("Arial", 18, "bold"), text_color="white")
        self.total_paid_label.pack(pady=(0, 1))
        paid_card.bind("<Button-1>", lambda _event, key="total_paid": self.show_debt_summary_detail(key))
        self.total_paid_label.bind("<Button-1>", lambda _event, key="total_paid": self.show_debt_summary_detail(key))
        
        # جدول الديون
        debts_frame = ctk.CTkFrame(tab)
        debts_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 1))
        debts_frame.grid_columnconfigure(0, weight=1)
        debts_frame.grid_rowconfigure(0, weight=1)
        
        # عنوان الجدول
        ctk.CTkLabel(
            debts_frame,
            text="📋 قائمة الديون",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, pady=(5, 0), sticky="w", padx=10)
        
        # Treeview للديون
        columns = ("id", "tracking_code", "customer", "phone", "device", "amount", "days", "actions")
        self.debts_tree = ttk.Treeview(debts_frame, columns=columns, show="headings", height=12)
        
        # تحسين الخط في قائمة الديون
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 9))
        style.configure("Treeview.Heading", font=("Arial", 9, "bold"))
        
        self.debts_tree.heading("id", text="#")
        self.debts_tree.heading("tracking_code", text="رقم التتبع")
        self.debts_tree.heading("customer", text="العميل")
        self.debts_tree.heading("phone", text="الهاتف")
        self.debts_tree.heading("device", text="الجهاز")
        self.debts_tree.heading("amount", text="المبلغ")
        self.debts_tree.heading("days", text="منذ")
        self.debts_tree.heading("actions", text="إجراءات")
        
        self.debts_tree.column("id", width=40, anchor=tk.CENTER)
        self.debts_tree.column("tracking_code", width=90, anchor=tk.CENTER)
        self.debts_tree.column("customer", width=120, anchor=tk.CENTER)
        self.debts_tree.column("phone", width=100, anchor=tk.CENTER)
        self.debts_tree.column("device", width=100, anchor=tk.CENTER)
        self.debts_tree.column("amount", width=80, anchor=tk.CENTER)
        self.debts_tree.column("days", width=60, anchor=tk.CENTER)
        self.debts_tree.column("actions", width=80, anchor=tk.CENTER)
        
        self.debts_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=2)
        
        # شريط التمرير
        scrollbar = ttk.Scrollbar(debts_frame, orient=tk.VERTICAL, command=self.debts_tree.yview)
        self.debts_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

        # ملصق معلومات التصفية
        self.debts_filter_info_label = ctk.CTkLabel(
            debts_frame,
            text="عرض: الديون غير المسددة (0 عنصر) | المجموع: 0.00 $",
            font=("Arial", 11)
        )
        self.debts_filter_info_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 5))
        
        # أزرار الإجراءات
        actions_frame = ctk.CTkFrame(debts_frame, fg_color="transparent")
        actions_frame.grid(row=3, column=0, columnspan=2, pady=2, sticky="ew")
        
        ctk.CTkButton(
            actions_frame,
            text="🔄 تحديث القائمة",
            command=self.load_debts_data,
            width=120
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(
            actions_frame,
            text="💰 تسجيل دفعة",
            command=self.mark_debt_as_paid,
            fg_color="#4caf50",
            hover_color="#45a049",
            width=120
        ).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkButton(
            actions_frame,
            text="📱 إرسال تذكير واتساب",
            command=self.send_debt_reminder,
            fg_color="#25d366",
            hover_color="#1da851",
            width=150
        ).pack(side=tk.LEFT, padx=5)
        
        # تحميل بيانات الديون
        self.load_debts_data()
    
    def load_debts_data(self):
        """تحميل بيانات الديون"""
        try:
            if not hasattr(self, 'maintenance_service'):
                return
            
            # جلب ملخص المدفوعات
            success, message, summary = self.maintenance_service.get_payment_summary()
            if success:
                self.total_debt_label.configure(text=f"{summary['total_unpaid']:.2f} $")
                self.debtors_count_label.configure(text=self.format_number_english(summary['unpaid_count']))
                self.total_paid_label.configure(text=f"{summary['total_paid']:.2f} $")
                self.debt_summary_data.update(summary)
            
            # جلب قائمة الديون غير المسددة
            success, message, debts = self.maintenance_service.get_unpaid_jobs()
            self.debts_data_unpaid = []
            if success and debts:
                for debt in debts:
                    amount_value = float(debt.get('final_cost', 0.0) or 0.0)
                    days_overdue = debt.get('days_overdue', 0)
                    self.debts_data_unpaid.append({
                        "id": debt.get('id'),
                        "tracking_code": debt.get('tracking_code'),
                        "customer_name": debt.get('customer_name'),
                        "customer_phone": debt.get('customer_phone'),
                        "device_type": debt.get('device_type'),
                        "final_cost": amount_value,
                        "days_display": f"{days_overdue} يوم",
                        "actions": "..."
                    })

            # جلب قائمة الطلبات المدفوعة (للتصفية عند الحاجة)
            self.debts_data_paid = []
            paid_success, paid_message, delivered_jobs = self.maintenance_service.search_jobs(status="delivered", limit=500)
            if paid_success and delivered_jobs:
                for job in delivered_jobs:
                    if job.get("payment_status") == "paid":
                        amount_value = float(job.get("final_cost") or job.get("estimated_cost") or 0.0)
                        delivered_at = job.get("delivered_at")
                        if delivered_at:
                            try:
                                delivered_str = delivered_at.strftime("%Y-%m-%d")
                            except AttributeError:
                                delivered_str = str(delivered_at)
                        else:
                            delivered_str = "--"
                        self.debts_data_paid.append({
                            "id": job.get('id'),
                            "tracking_code": job.get('tracking_code'),
                            "customer_name": job.get('customer_name'),
                            "customer_phone": job.get('customer_phone'),
                            "device_type": job.get('device_type'),
                            "final_cost": amount_value,
                            "days_display": f"تم التسليم {delivered_str}",
                            "actions": "تم الدفع"
                        })

            # تطبيق التصفية الحالية (أو الافتراضية)
            self.apply_debt_filter(self.current_debt_filter, show_message=False)
        except Exception as e:
            print(f"خطأ في تحميل بيانات الديون: {str(e)}")

    def refresh_debts_tree(self, data: List[Dict[str, Any]], title: str, total_amount: float):
        """تحديث جدول الديون بناءً على البيانات المفلترة"""
        if not getattr(self, 'debts_tree', None):
            return

        # مسح العناصر القديمة
        for item in self.debts_tree.get_children():
            self.debts_tree.delete(item)

        for debt in data:
            amount_value = float(debt.get("final_cost", 0.0) or 0.0)
            days_display = debt.get("days_display") or f"{debt.get('days_overdue', 0)} يوم"
            actions_display = debt.get("actions", "...")

            self.debts_tree.insert("", tk.END, values=(
                debt.get("id"),
                debt.get("tracking_code"),
                debt.get("customer_name"),
                debt.get("customer_phone"),
                debt.get("device_type"),
                f"{amount_value:.2f} $",
                days_display,
                actions_display
            ))

        if getattr(self, 'debts_filter_info_label', None):
            count = len(data)
            self.debts_filter_info_label.configure(
                text=f"عرض: {title} ({self.format_number_english(count)} عنصر) | المجموع: {total_amount:.2f} $"
            )

    def apply_debt_filter(self, filter_key: str, show_message: bool = True):
        """تطبيق تصفية على قائمة الديون"""
        if filter_key == "paid" and self.debts_data_paid:
            data = self.debts_data_paid
            title = "المدفوعات المكتملة"
        elif filter_key == "paid":
            data = self.debts_data_unpaid
            title = "الديون غير المسددة"
            filter_key = "unpaid"
        else:
            data = self.debts_data_unpaid
            title = "الديون غير المسددة"
            filter_key = "unpaid"

        total_amount = sum(float(item.get("final_cost", 0.0) or 0.0) for item in data)
        count = len(data)

        self.current_debt_filter = filter_key
        self.refresh_debts_tree(data, title, total_amount)

        if show_message:
            messagebox.showinfo(
                "نتائج التصفية",
                f"{title}\nالعدد: {self.format_number_english(count)}\nالإجمالي: {total_amount:.2f} $"
            )

    def show_debt_summary_detail(self, key: str):
        """تصفية قائمة الديون بناءً على البطاقة المختارة"""
        if key in ("total_unpaid", "unpaid_count"):
            self.apply_debt_filter("unpaid")
        elif key == "total_paid":
            self.apply_debt_filter("paid")
        else:
            self.apply_debt_filter(self.current_debt_filter)
    
    def mark_debt_as_paid(self):
        """تسجيل دفعة لدين محدد"""
        selected = self.debts_tree.selection()
        if not selected:
            messagebox.showwarning("تحذير", "الرجاء اختيار دين لتسجيل الدفعة")
            return
        
        item = self.debts_tree.item(selected[0])
        job_id = item['values'][0]
        
        # نافذة تأكيد طريقة الدفع
        dialog = ctk.CTkToplevel(self)
        dialog.title("💰 تسجيل الدفعة")
        dialog.geometry("400x250")
        dialog.grab_set()
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        ctk.CTkLabel(dialog, text="💰 اختر طريقة الدفع:", font=("Arial", 14, "bold")).pack(pady=10)
        
        payment_method_var = tk.StringVar(value="cash")
        
        ctk.CTkRadioButton(
            dialog,
            text="💵 كاش",
            variable=payment_method_var,
            value="cash",
            font=("Arial", 12)
        ).pack(anchor=tk.W, padx=40, pady=2)
        
        ctk.CTkRadioButton(
            dialog,
            text="💳 Wish Money",
            variable=payment_method_var,
            value="wish_money",
            font=("Arial", 12)
        ).pack(anchor=tk.W, padx=40, pady=2)
        
        def confirm_payment():
            try:
                success, message = self.maintenance_service.update_payment_status(
                    job_id=job_id,
                    payment_status="paid",
                    payment_method=payment_method_var.get()
                )
                
                if success:
                    messagebox.showinfo("نجاح", "✅ تم تسجيل الدفعة بنجاح!")
                    dialog.destroy()
                    self.load_debts_data()
                    self.load_data()  # تحديث الجدول الرئيسي
                else:
                    messagebox.showerror("خطأ", f"❌ فشل في تسجيل الدفعة: {message}")
            except Exception as e:
                messagebox.showerror("خطأ", f"❌ حدث خطأ: {str(e)}")
        
        ctk.CTkButton(
            dialog,
            text="تأكيد الدفع",
            command=confirm_payment,
            fg_color="#4caf50",
            hover_color="#45a049"
        ).pack(pady=10)
    
    def send_debt_reminder(self):
        """إرسال تذكير واتساب للمدينين"""
        selected = self.debts_tree.selection()
        if not selected:
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل لإرسال التذكير")
            return
        
        item = self.debts_tree.item(selected[0])
        phone = item['values'][3]
        amount = item['values'][5]
        customer_name = item['values'][2]
        
        # رسالة التذكير
        message = f"مرحباً {customer_name}،\n\nهذا تذكير بديون غير مسددة بمبلغ {amount}\n\nنرجو منكم التكرم بالسداد في أقرب وقت ممكن.\n\nشكراً لتعاونكم 🙏"
        
        # فتح واتساب
        import urllib.parse
        import webbrowser
        
        messagebox.showinfo("تم", "📱 تم إرسال التذكير")
    
    def toggle_weekly_reminders(self):
        """تبديل حالة التذكيرات الأسبوعية"""
        if not hasattr(self, 'debt_reminder_service'):
            messagebox.showerror("خطأ", "خدمة التذكيرات غير متاحة")
            return
        
        self.reminders_enabled = not self.reminders_enabled
        
        if self.reminders_enabled:
            # تفعيل التذكيرات
            self.debt_reminder_service.start()
            self.btn_reminders.configure(
                text="📅 تذكيرات مفعّلة ✅",
                fg_color="#4caf50",
                hover_color="#45a049"
            )
            messagebox.showinfo(
                "تم التفعيل", 
                "✅ تم تفعيل التذكيرات الأسبوعية!\n\n"
                "📅 سيتم إرسال تذكيرات واتساب تلقائياً:\n"
                "• كل يوم أحد الساعة 10:00 صباحاً\n"
                "• للمدينين الذين مر على ديونهم 3 أيام أو أكثر\n\n"
                "💡 يمكنك إيقاف التذكيرات بالضغط على الزر مرة أخرى"
            )
        else:
            # إيقاف التذكيرات
            self.debt_reminder_service.stop()
            self.btn_reminders.configure(
                text="📅 تذكيرات أسبوعية",
                fg_color="#607d8b",
                hover_color="#455a64"
            )
            messagebox.showinfo("تم الإيقاف", "⏹️ تم إيقاف التذكيرات الأسبوعية")
    
    def setup_reports_tab(self):
        """إعداد علامة تبويب التقارير - واجهة شاملة"""
        if hasattr(self, 'tabview'):
            tab = self.tabview.tab("التقارير")
        else:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        
        # إطار التحكم في التقرير
        control_frame = ctk.CTkFrame(tab)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        control_frame.grid_columnconfigure((1, 3, 5, 7), weight=1)
        
        # نوع التقرير
        ctk.CTkLabel(control_frame, text="نوع التقرير:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.report_type_var = tk.StringVar(value="daily")
        report_type_options = ["daily", "weekly"]
        if self.monthly_stats_enabled:
            report_type_options.append("monthly")
        report_type_options.extend(["yearly", "custom"])
        report_type_combo = ctk.CTkComboBox(
            control_frame,
            values=report_type_options,
            variable=self.report_type_var,
            width=150,
            command=self.on_report_type_changed
        )
        report_type_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # نوع الجهاز
        ctk.CTkLabel(control_frame, text="نوع الجهاز:", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.code_type_var = tk.StringVar(value="all")
        code_type_combo = ctk.CTkComboBox(
            control_frame,
            values=["all", "A", "B", "C", "D"],
            variable=self.code_type_var,
            width=100,
            command=self.on_filter_changed
        )
        code_type_combo.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        
        # الحالة
        ctk.CTkLabel(control_frame, text="الحالة:", font=("Arial", 12, "bold")).grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.status_filter_var = tk.StringVar(value="delivered")
        status_combo = ctk.CTkComboBox(
            control_frame,
            values=["delivered", "all"],
            variable=self.status_filter_var,
            width=120,
            command=self.on_filter_changed
        )
        status_combo.grid(row=0, column=5, padx=5, pady=5, sticky="ew")
        
        # تواريخ مخصصة (مخفية افتراضياً)
        self.custom_date_frame = ctk.CTkFrame(control_frame)
        self.custom_date_frame.grid(row=1, column=0, columnspan=6, sticky="ew", padx=5, pady=5)
        self.custom_date_frame.grid_columnconfigure((1, 3), weight=1)
        self.custom_date_frame.grid_remove()  # مخفي افتراضياً
        
        ctk.CTkLabel(self.custom_date_frame, text="من:", font=("Arial", 11)).grid(row=0, column=0, padx=5, pady=5)
        self.start_date_entry = ctk.CTkEntry(self.custom_date_frame, width=120, placeholder_text="YYYY-MM-DD")
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.start_date_entry.bind("<Return>", lambda e: self.on_filter_changed())
        
        ctk.CTkLabel(self.custom_date_frame, text="إلى:", font=("Arial", 11)).grid(row=0, column=2, padx=5, pady=5)
        self.end_date_entry = ctk.CTkEntry(self.custom_date_frame, width=120, placeholder_text="YYYY-MM-DD")
        self.end_date_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        self.end_date_entry.bind("<Return>", lambda e: self.on_filter_changed())
        
        # أزرار التحكم
        buttons_frame = ctk.CTkFrame(control_frame)
        buttons_frame.grid(row=0, column=6, rowspan=2, padx=5, pady=5)
        
        ctk.CTkButton(
            buttons_frame,
            text="تحديث التقرير",
            command=self.generate_advanced_report,
            width=120,
            fg_color="#2196F3",
            hover_color="#1976D2"
        ).pack(padx=5, pady=2)
        
        ctk.CTkButton(
            buttons_frame,
            text="تصدير PDF",
            command=self.export_report_pdf,
            width=120,
            fg_color="#4CAF50",
            hover_color="#45a049"
        ).pack(padx=5, pady=2)
        
        ctk.CTkButton(
            buttons_frame,
            text="تصدير Excel",
            command=self.export_report_excel,
            width=120,
            fg_color="#FF9800",
            hover_color="#F57C00"
        ).pack(padx=5, pady=2)
        
        ctk.CTkButton(
            buttons_frame,
            text="طباعة",
            command=self.print_report,
            width=120,
            fg_color="#9C27B0",
            hover_color="#7B1FA2"
        ).pack(padx=5, pady=2)
        
        # إطار المحتوى الرئيسي
        content_frame = ctk.CTkFrame(tab)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)
        
        # إطار الملخص التنفيذي
        self.summary_frame = ctk.CTkFrame(content_frame, fg_color="#E3F2FD", corner_radius=10)
        self.summary_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.summary_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # إطار المحتوى (الرسوم البيانية فقط)
        main_content_frame = ctk.CTkFrame(content_frame)
        main_content_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        main_content_frame.grid_columnconfigure(0, weight=1)
        main_content_frame.grid_rowconfigure(0, weight=1)
        
        # إطار الرسوم البيانية
        charts_frame = ctk.CTkFrame(main_content_frame)
        charts_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        charts_frame.grid_columnconfigure(0, weight=1)
        charts_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(charts_frame, text="📊 الرسوم البيانية", font=("Arial", 16, "bold")).pack(pady=10)
        
        # إطار للرسوم البيانية (سيتم ملؤه لاحقاً)
        self.charts_container = ctk.CTkFrame(charts_frame)
        self.charts_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # تهيئة التقرير الافتراضي
        self.current_report_data = None
        # سيتم تحميل التقرير عند فتح التبويب أو عند الضغط على "تحديث التقرير"
    
    def format_number_english(self, number):
        """تحويل رقم إلى سلسلة نصية بالأرقام الإنجليزية (0-9) دائماً"""
        if number is None:
            return "0"
        
        # تحويل الرقم إلى سلسلة نصية
        number_str = str(number)
        
        # جدول تحويل الأرقام العربية إلى الإنجليزية
        arabic_to_english = {
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        }
        
        # تحويل أي أرقام عربية أو فارسية إلى إنجليزية
        result = ''.join(arabic_to_english.get(char, char) for char in number_str)
        
        return result
    
    def translate_status_to_arabic(self, status):
        """ترجمة حالة الجهاز إلى العربية"""
        status_translations = {
            'received': 'تم الاستلام',
            'not_repaired': 'لم تتم الصيانة',
            'repaired': 'تم الصيانة',
            'delivered': 'تم التسليم'
        }
        return status_translations.get(status, status)
    
    def create_status_bar(self):
        """إنشاء شريط الحالة"""
        status_bar = ctk.CTkFrame(self, height=25)
        status_bar.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        
        self.status_label = ctk.CTkLabel(status_bar, text="جاهز")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.status_count = ctk.CTkLabel(status_bar, text=f"{self.format_number_english(0)} عنصر")
        self.status_count.pack(side=tk.RIGHT, padx=10)
    
    def show_vip_accounts(self):
        """إظهار نافذة حسابات العملاء المميزين"""
        from gui.vip_accounts_window import VIPAccountsWindow
        vip_window = VIPAccountsWindow(self)
        # حفظ مرجع للنافذة لتحديثها لاحقاً
        if not hasattr(self, 'open_vip_windows'):
            self.open_vip_windows = []
        self.open_vip_windows.append(vip_window)
    
    def show_whatsapp_broadcast_settings(self):
        """إظهار نافذة إدارة رسائل الواتساب الجماعية"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("إدارة الرسائل الجماعية - ADR ELECTRONICS")
        dialog.geometry("800x600")
        dialog.grab_set()
        dialog.resizable(True, True)
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # محتوى النافذة
        main_container = ctk.CTkFrame(dialog, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # عنوان النافذة
        title_frame = ctk.CTkFrame(main_container, fg_color="#25D366", corner_radius=10)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(
            title_frame, 
            text="📢 إدارة الرسائل الجماعية", 
            font=("Arial", 18, "bold"), 
            text_color="white"
        ).pack(pady=10)
        
        # إطار المحتوى الرئيسي
        content_frame = ctk.CTkFrame(main_container, fg_color="#fafafa", corner_radius=10)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # تبويبات للإعدادات المختلفة
        tabview = ctk.CTkTabview(content_frame, width=750, height=500)
        tabview.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # تبويب الرسائل التلقائية
        tab_auto = tabview.add("📱 الرسائل التلقائية")
        self.setup_auto_messages_tab(tab_auto)
        
        # تبويب الرسائل الجماعية
        tab_broadcast = tabview.add("📢 الرسائل الجماعية")
        self.setup_broadcast_tab(tab_broadcast)
        
        # تبويب الإعدادات
        tab_settings = tabview.add("⚙️ الإعدادات")
        self.setup_broadcast_settings_tab(tab_settings)
        
        # تعيين التبويب الافتراضي
        tabview.set("📱 الرسائل التلقائية")
    def setup_auto_messages_tab(self, parent):
        """إعداد تبويب الرسائل التلقائية"""
        # إطار الرسائل التلقائية
        auto_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        auto_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # عنوان القسم
        ctk.CTkLabel(
            auto_frame,
            text="📱 رسائل التحديث التلقائية",
            font=("Arial", 16, "bold"),
            text_color="#25D366"
        ).pack(anchor=tk.W, pady=(0, 15))
        
        # وصف القسم
        ctk.CTkLabel(
            auto_frame,
            text="هذه الرسائل ترسل تلقائياً عند تحديث حالة الجهاز",
            font=("Arial", 12),
            text_color="#666666"
        ).pack(anchor=tk.W, pady=(0, 20))
        
        # رسالة تم الاستلام
        received_frame = ctk.CTkFrame(auto_frame, fg_color="#E8F5E8", corner_radius=8)
        received_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            received_frame,
            text="📥 رسالة تم الاستلام",
            font=("Arial", 14, "bold"),
            text_color="#2E7D32"
        ).pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        self.received_message_text = ctk.CTkTextbox(
            received_frame,
            height=100,
            font=("Arial", 11)
        )
        self.received_message_text.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # رسالة تمت الصيانة
        repaired_frame = ctk.CTkFrame(auto_frame, fg_color="#FFF3E0", corner_radius=8)
        repaired_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            repaired_frame,
            text="🔧 رسالة تمت الصيانة",
            font=("Arial", 14, "bold"),
            text_color="#F57C00"
        ).pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        self.repaired_message_text = ctk.CTkTextbox(
            repaired_frame,
            height=100,
            font=("Arial", 11)
        )
        self.repaired_message_text.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # رسالة تم التسليم
        delivered_frame = ctk.CTkFrame(auto_frame, fg_color="#E3F2FD", corner_radius=8)
        delivered_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            delivered_frame,
            text="✅ رسالة تم التسليم",
            font=("Arial", 14, "bold"),
            text_color="#1976D2"
        ).pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        self.delivered_message_text = ctk.CTkTextbox(
            delivered_frame,
            height=100,
            font=("Arial", 11)
        )
        self.delivered_message_text.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        # أزرار التحكم
        buttons_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ctk.CTkButton(
            buttons_frame,
            text="💾 حفظ الرسائل",
            command=self.save_auto_messages,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=120
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ctk.CTkButton(
            buttons_frame,
            text="🔄 إعادة تعيين",
            command=self.reset_auto_messages,
            fg_color="#757575",
            hover_color="#616161",
            width=120
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # تحميل الرسائل الحالية
        self.load_auto_messages()
    
    def setup_broadcast_tab(self, parent):
        """إعداد تبويب الرسائل الجماعية"""
        # إطار الرسائل الجماعية
        broadcast_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        broadcast_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # عنوان القسم
        ctk.CTkLabel(
            broadcast_frame,
            text="📢 الرسائل الجماعية",
            font=("Arial", 16, "bold"),
            text_color="#25D366"
        ).pack(anchor=tk.W, pady=(0, 15))
        
        # وصف القسم
        ctk.CTkLabel(
            broadcast_frame,
            text="إرسال رسالة واحدة لجميع العملاء أو مجموعة محددة",
            font=("Arial", 12),
            text_color="#666666"
        ).pack(anchor=tk.W, pady=(0, 20))
        
        # اختيار نوع الإرسال
        send_type_frame = ctk.CTkFrame(broadcast_frame, fg_color="transparent")
        send_type_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            send_type_frame,
            text="نوع الإرسال:",
            font=("Arial", 12, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))
        
        self.send_type_var = tk.StringVar(value="all")
        
        ctk.CTkRadioButton(
            send_type_frame,
            text="جميع العملاء",
            variable=self.send_type_var,
            value="all",
            font=("Arial", 11)
        ).pack(anchor=tk.W, pady=2)
        
        ctk.CTkRadioButton(
            send_type_frame,
            text="عملاء محددون",
            variable=self.send_type_var,
            value="specific",
            font=("Arial", 11)
        ).pack(anchor=tk.W, pady=2)
        
        # حقل الرسالة
        message_frame = ctk.CTkFrame(broadcast_frame, fg_color="transparent")
        message_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            message_frame,
            text="نص الرسالة:",
            font=("Arial", 12, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))
        
        self.broadcast_message_text = ctk.CTkTextbox(
            message_frame,
            height=150,
            font=("Arial", 11)
        )
        self.broadcast_message_text.pack(fill=tk.X, pady=(0, 10))

        # قسم إدارة القوالب
        templates_frame = ctk.CTkFrame(broadcast_frame, fg_color="#F5F5F5", corner_radius=8)
        templates_frame.pack(fill=tk.X, pady=(0, 15))

        ctk.CTkLabel(
            templates_frame,
            text="📝 إدارة قوالب الرسائل",
            font=("Arial", 14, "bold"),
            text_color="#25D366"
        ).pack(anchor=tk.W, padx=15, pady=(10, 5))

        # إطار القوالب
        templates_content_frame = ctk.CTkFrame(templates_frame, fg_color="transparent")
        templates_content_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        # قائمة القوالب
        templates_list_frame = ctk.CTkFrame(templates_content_frame, fg_color="white", corner_radius=5)
        templates_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ctk.CTkLabel(
            templates_list_frame,
            text="القوالب المحفوظة:",
            font=("Arial", 11, "bold")
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        # قائمة القوالب
        self.broadcast_templates_listbox = tk.Listbox(
            templates_list_frame,
            height=4,
            font=("Arial", 10),
            selectmode=tk.SINGLE
        )
        self.broadcast_templates_listbox.pack(fill=tk.X, padx=10, pady=(0, 10))

        # أزرار إدارة القوالب
        templates_buttons_frame = ctk.CTkFrame(templates_content_frame, fg_color="transparent")
        templates_buttons_frame.pack(fill=tk.X)

        ctk.CTkButton(
            templates_buttons_frame,
            text="💾 حفظ قالب جديد",
            command=self.save_broadcast_template,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=130,
            height=30,
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=(0, 5))

        ctk.CTkButton(
            templates_buttons_frame,
            text="📂 تحميل قالب",
            command=self.load_broadcast_template,
            fg_color="#2196F3",
            hover_color="#1976D2",
            width=130,
            height=30,
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=(0, 5))

        ctk.CTkButton(
            templates_buttons_frame,
            text="✏️ حفظ التعديلات",
            command=self.update_broadcast_template,
            fg_color="#FF9800",
            hover_color="#F57C00",
            width=130,
            height=30,
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=(0, 5))

        ctk.CTkButton(
            templates_buttons_frame,
            text="🗑️ حذف قالب",
            command=self.delete_broadcast_template,
            fg_color="#F44336",
            hover_color="#D32F2F",
            width=130,
            height=30,
            font=("Arial", 10)
        ).pack(side=tk.LEFT, padx=(0, 5))

        # تحميل القوالب المحفوظة
        self.load_broadcast_templates_list()

        # أزرار التحكم
        buttons_frame = ctk.CTkFrame(broadcast_frame, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ctk.CTkButton(
            buttons_frame,
            text="📤 إرسال للجميع",
            command=self.send_broadcast_message,
            fg_color="#25D366",
            hover_color="#128C7E",
            width=120
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ctk.CTkButton(
            buttons_frame,
            text="👥 إرسال محدد",
            command=self.send_specific_message,
            fg_color="#FF9800",
            hover_color="#F57C00",
            width=120
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ctk.CTkButton(
            buttons_frame,
            text="📋 معاينة",
            command=self.preview_broadcast_message,
            fg_color="#2196F3",
            hover_color="#1976D2",
            width=120
        ).pack(side=tk.LEFT, padx=(0, 10))
    
    def setup_broadcast_settings_tab(self, parent):
        """إعداد تبويب إعدادات الرسائل الجماعية"""
        # إطار الإعدادات
        settings_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # عنوان القسم
        ctk.CTkLabel(
            settings_frame,
            text="⚙️ إعدادات الرسائل الجماعية",
            font=("Arial", 16, "bold"),
            text_color="#25D366"
        ).pack(anchor=tk.W, pady=(0, 15))
        
        # إعدادات الإرسال التلقائي
        auto_send_frame = ctk.CTkFrame(settings_frame, fg_color="#E8F5E8", corner_radius=8)
        auto_send_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            auto_send_frame,
            text="📤 الإرسال التلقائي",
            font=("Arial", 14, "bold"),
            text_color="#2E7D32"
        ).pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        self.auto_send_enabled = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            auto_send_frame,
            text="تفعيل الإرسال التلقائي عند تحديث الحالة",
            variable=self.auto_send_enabled,
            font=("Arial", 11)
        ).pack(anchor=tk.W, padx=15, pady=(0, 10))
        
        # إعدادات التوقيت
        timing_frame = ctk.CTkFrame(settings_frame, fg_color="#FFF3E0", corner_radius=8)
        timing_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(
            timing_frame,
            text="⏰ إعدادات التوقيت",
            font=("Arial", 14, "bold"),
            text_color="#F57C00"
        ).pack(anchor=tk.W, padx=15, pady=(10, 5))
        
        # تأخير الإرسال
        delay_frame = ctk.CTkFrame(timing_frame, fg_color="transparent")
        delay_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        
        ctk.CTkLabel(
            delay_frame,
            text="تأخير الإرسال (ثواني):",
            font=("Arial", 11)
        ).pack(side=tk.LEFT)
        
        self.send_delay_var = tk.StringVar(value="5")
        delay_entry = ctk.CTkEntry(
            delay_frame,
            textvariable=self.send_delay_var,
            width=80
        )
        delay_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # أزرار التحكم
        buttons_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ctk.CTkButton(
            buttons_frame,
            text="💾 حفظ الإعدادات",
            command=self.save_broadcast_settings,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=120
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ctk.CTkButton(
            buttons_frame,
            text="🔄 إعادة تعيين",
            command=self.reset_broadcast_settings,
            fg_color="#757575",
            hover_color="#616161",
            width=120
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # تحميل الإعدادات الحالية
        self.load_broadcast_settings()
    
    def load_auto_messages(self):
        """تحميل الرسائل التلقائية من قاعدة البيانات"""
        try:
            if hasattr(self, 'maintenance_service'):
                # رسالة تم الاستلام
                received_msg = self.maintenance_service.get_system_setting(
                    "whatsapp_received_message",
                    WHATSAPP_RECEIVED_MESSAGE
                )
                self.received_message_text.delete("1.0", tk.END)
                self.received_message_text.insert("1.0", received_msg)
                
                # رسالة تمت الصيانة
                repaired_msg = self.maintenance_service.get_system_setting(
                    "whatsapp_repaired_message",
                    WHATSAPP_REPAIRED_MESSAGE
                )
                self.repaired_message_text.delete("1.0", tk.END)
                self.repaired_message_text.insert("1.0", repaired_msg)
                
                # رسالة تم التسليم
                delivered_msg = self.maintenance_service.get_system_setting(
                    "whatsapp_delivered_message",
                    WHATSAPP_DELIVERED_MESSAGE
                )
                self.delivered_message_text.delete("1.0", tk.END)
                self.delivered_message_text.insert("1.0", delivered_msg)
        except Exception as e:
            print(f"خطأ في تحميل الرسائل التلقائية: {e}")
    
    def save_auto_messages(self):
        """حفظ الرسائل التلقائية في قاعدة البيانات"""
        try:
            if hasattr(self, 'maintenance_service'):
                # حفظ رسالة تم الاستلام
                received_msg = self.received_message_text.get("1.0", tk.END).strip()
                self.maintenance_service.set_system_setting(
                    "whatsapp_received_message",
                    received_msg,
                    "رسالة تم الاستلام"
                )
                
                # حفظ رسالة تمت الصيانة
                repaired_msg = self.repaired_message_text.get("1.0", tk.END).strip()
                self.maintenance_service.set_system_setting(
                    "whatsapp_repaired_message",
                    repaired_msg,
                    "رسالة تمت الصيانة"
                )
                
                # حفظ رسالة تم التسليم
                delivered_msg = self.delivered_message_text.get("1.0", tk.END).strip()
                self.maintenance_service.set_system_setting(
                    "whatsapp_delivered_message",
                    delivered_msg,
                    "رسالة تم التسليم"
                )
                
                messagebox.showinfo("نجح", "تم حفظ الرسائل التلقائية بنجاح!")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حفظ الرسائل: {str(e)}")
    
    def reset_auto_messages(self):
        """إعادة تعيين الرسائل التلقائية للقيم الافتراضية"""
        try:
            # رسالة تم الاستلام الافتراضية
            default_received = WHATSAPP_RECEIVED_MESSAGE
            self.received_message_text.delete("1.0", tk.END)
            self.received_message_text.insert("1.0", default_received)
            
            # رسالة تمت الصيانة الافتراضية
            default_repaired = WHATSAPP_REPAIRED_MESSAGE
            self.repaired_message_text.delete("1.0", tk.END)
            self.repaired_message_text.insert("1.0", default_repaired)
            
            # رسالة تم التسليم الافتراضية
            default_delivered = WHATSAPP_DELIVERED_MESSAGE
            self.delivered_message_text.delete("1.0", tk.END)
            self.delivered_message_text.insert("1.0", default_delivered)
            
            messagebox.showinfo("نجح", "تم إعادة تعيين الرسائل للقيم الافتراضية!")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في إعادة التعيين: {str(e)}")
    
    def send_broadcast_message(self):
        """إرسال رسالة جماعية لجميع العملاء"""
        try:
            message = self.broadcast_message_text.get("1.0", tk.END).strip()
            if not message:
                messagebox.showwarning("تحذير", "يرجى كتابة رسالة قبل الإرسال")
                return
            
            if not messagebox.askyesno("تأكيد", "هل تريد إرسال هذه الرسالة لجميع العملاء؟"):
                return
            
            # جلب جميع العملاء
            db = next(get_db())
            customers = db.query(Customer).all()
            db.close()
            
            if not customers:
                messagebox.showwarning("تحذير", "لا يوجد عملاء في النظام")
                return
            
            # إرسال الرسالة لكل عميل
            sent_count = 0
            for customer in customers:
                try:
                    phone = customer.phone.replace('+', '').replace(' ', '').replace('-', '')
                    if not phone.startswith('961'):
                        phone = '961' + phone.lstrip('0')
                    
                    whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
                    webbrowser.open(whatsapp_url)
                    sent_count += 1
                    
                    # تأخير قصير بين الرسائل
                    import time
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"خطأ في إرسال رسالة للعميل {customer.name}: {e}")
            
            messagebox.showinfo("نجح", f"تم فتح الواتساب لإرسال الرسالة لـ {sent_count} عميل")
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في إرسال الرسالة الجماعية: {str(e)}")
    
    def send_specific_message(self):
        """إرسال رسالة لعملاء محددين"""
        try:
            message = self.broadcast_message_text.get("1.0", tk.END).strip()
            if not message:
                messagebox.showwarning("تحذير", "يرجى كتابة رسالة قبل الإرسال")
                return
            
            # إنشاء نافذة اختيار العملاء
            self.show_customer_selection_dialog(message)
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في إرسال الرسالة المحددة: {str(e)}")
    
    def preview_broadcast_message(self):
        """معاينة الرسالة الجماعية"""
        try:
            message = self.broadcast_message_text.get("1.0", tk.END).strip()
            if not message:
                messagebox.showwarning("تحذير", "يرجى كتابة رسالة قبل المعاينة")
                return
            
            # إنشاء نافذة معاينة
            preview_dialog = ctk.CTkToplevel(self)
            preview_dialog.title("معاينة الرسالة")
            preview_dialog.geometry("500x400")
            preview_dialog.grab_set()
            
            # إعداد التنقل بالـ Enter
            self.setup_enter_navigation(preview_dialog)
            
            # عنوان النافذة
            ctk.CTkLabel(
                preview_dialog,
                text="📋 معاينة الرسالة",
                font=("Arial", 16, "bold"),
                text_color="#25D366"
            ).pack(pady=10)
            
            # عرض الرسالة
            message_frame = ctk.CTkFrame(preview_dialog, fg_color="#f0f0f0", corner_radius=8)
            message_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
            
            ctk.CTkLabel(
                message_frame,
                text=message,
                font=("Arial", 12),
                text_color="#333333",
                justify=tk.LEFT,
                wraplength=450
            ).pack(pady=20, padx=20)
            
            # زر الإغلاق
            ctk.CTkButton(
                preview_dialog,
                text="إغلاق",
                command=preview_dialog.destroy,
                fg_color="#757575",
                hover_color="#616161"
            ).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في معاينة الرسالة: {str(e)}")
    
    def load_broadcast_templates_list(self):
        """تحميل قائمة القوالب المحفوظة"""
        try:
            if not hasattr(self, 'broadcast_templates_listbox'):
                return
                
            self.broadcast_templates_listbox.delete(0, tk.END)
            
            if hasattr(self, 'maintenance_service'):
                templates_json = self.maintenance_service.get_system_setting(
                    "broadcast_templates",
                    "{}"
                )
                
                if templates_json:
                    templates = json.loads(templates_json)
                    for template_name in sorted(templates.keys()):
                        self.broadcast_templates_listbox.insert(tk.END, template_name)
        except Exception as e:
            print(f"خطأ في تحميل قائمة القوالب: {str(e)}")
    
    def save_broadcast_template(self):
        """حفظ قالب رسالة جديد"""
        try:
            message = self.broadcast_message_text.get("1.0", tk.END).strip()
            if not message:
                messagebox.showwarning("تحذير", "يرجى كتابة رسالة قبل الحفظ")
                return
            
            # طلب اسم القالب
            template_name = simpledialog.askstring(
                "حفظ قالب جديد",
                "أدخل اسم القالب:"
            )
            
            if not template_name:
                return
            
            if hasattr(self, 'maintenance_service'):
                # جلب القوالب الحالية
                templates_json = self.maintenance_service.get_system_setting(
                    "broadcast_templates",
                    "{}"
                )
                templates = json.loads(templates_json) if templates_json else {}
                
                # إضافة القالب الجديد
                templates[template_name] = message
                
                # حفظ القوالب
                self.maintenance_service.set_system_setting(
                    "broadcast_templates",
                    json.dumps(templates, ensure_ascii=False),
                    "قوالب الرسائل الجماعية"
                )
                
                # تحديث القائمة
                self.load_broadcast_templates_list()
                
                messagebox.showinfo("نجح", f"تم حفظ القالب '{template_name}' بنجاح!")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حفظ القالب: {str(e)}")
    
    def load_broadcast_template(self):
        """تحميل قالب محفوظ"""
        try:
            if not hasattr(self, 'broadcast_templates_listbox'):
                return
            
            selection = self.broadcast_templates_listbox.curselection()
            if not selection:
                messagebox.showwarning("تحذير", "يرجى اختيار قالب من القائمة")
                return
            
            template_name = self.broadcast_templates_listbox.get(selection[0])
            
            if hasattr(self, 'maintenance_service'):
                # جلب القوالب
                templates_json = self.maintenance_service.get_system_setting(
                    "broadcast_templates",
                    "{}"
                )
                templates = json.loads(templates_json) if templates_json else {}
                
                if template_name in templates:
                    # تحميل القالب في حقل الرسالة
                    self.broadcast_message_text.delete("1.0", tk.END)
                    self.broadcast_message_text.insert("1.0", templates[template_name])
                    messagebox.showinfo("نجح", f"تم تحميل القالب '{template_name}' بنجاح!")
                else:
                    messagebox.showerror("خطأ", "القالب غير موجود")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تحميل القالب: {str(e)}")
    
    def update_broadcast_template(self):
        """تحديث قالب موجود"""
        try:
            if not hasattr(self, 'broadcast_templates_listbox'):
                return
            
            selection = self.broadcast_templates_listbox.curselection()
            if not selection:
                messagebox.showwarning("تحذير", "يرجى اختيار قالب من القائمة لتحديثه")
                return
            
            template_name = self.broadcast_templates_listbox.get(selection[0])
            message = self.broadcast_message_text.get("1.0", tk.END).strip()
            
            if not message:
                messagebox.showwarning("تحذير", "يرجى كتابة رسالة قبل الحفظ")
                return
            
            if not messagebox.askyesno("تأكيد", f"هل تريد تحديث القالب '{template_name}'؟"):
                return
            
            if hasattr(self, 'maintenance_service'):
                # جلب القوالب الحالية
                templates_json = self.maintenance_service.get_system_setting(
                    "broadcast_templates",
                    "{}"
                )
                templates = json.loads(templates_json) if templates_json else {}
                
                if template_name in templates:
                    # تحديث القالب
                    templates[template_name] = message
                    
                    # حفظ القوالب
                    self.maintenance_service.set_system_setting(
                        "broadcast_templates",
                        json.dumps(templates, ensure_ascii=False),
                        "قوالب الرسائل الجماعية"
                    )
                    
                    messagebox.showinfo("نجح", f"تم تحديث القالب '{template_name}' بنجاح!")
                else:
                    messagebox.showerror("خطأ", "القالب غير موجود")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تحديث القالب: {str(e)}")
    
    def delete_broadcast_template(self):
        """حذف قالب محفوظ"""
        try:
            if not hasattr(self, 'broadcast_templates_listbox'):
                return
            
            selection = self.broadcast_templates_listbox.curselection()
            if not selection:
                messagebox.showwarning("تحذير", "يرجى اختيار قالب من القائمة لحذفه")
                return
            
            template_name = self.broadcast_templates_listbox.get(selection[0])
            
            if not messagebox.askyesno("تأكيد", f"هل تريد حذف القالب '{template_name}'؟"):
                return
            
            if hasattr(self, 'maintenance_service'):
                # جلب القوالب الحالية
                templates_json = self.maintenance_service.get_system_setting(
                    "broadcast_templates",
                    "{}"
                )
                templates = json.loads(templates_json) if templates_json else {}
                
                if template_name in templates:
                    # حذف القالب
                    del templates[template_name]
                    
                    # حفظ القوالب
                    self.maintenance_service.set_system_setting(
                        "broadcast_templates",
                        json.dumps(templates, ensure_ascii=False),
                        "قوالب الرسائل الجماعية"
                    )
                    
                    # تحديث القائمة
                    self.load_broadcast_templates_list()
                    
                    messagebox.showinfo("نجح", f"تم حذف القالب '{template_name}' بنجاح!")
                else:
                    messagebox.showerror("خطأ", "القالب غير موجود")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حذف القالب: {str(e)}")
    def show_customer_selection_dialog(self, message):
        """عرض نافذة اختيار العملاء"""
        try:
            # جلب جميع العملاء
            db = next(get_db())
            customers = db.query(Customer).all()
            db.close()
            
            if not customers:
                messagebox.showwarning("تحذير", "لا يوجد عملاء في النظام")
                return
            
            # إنشاء نافذة اختيار العملاء
            selection_dialog = ctk.CTkToplevel(self)
            selection_dialog.title("اختيار العملاء")
            selection_dialog.geometry("600x500")
            selection_dialog.grab_set()
            
            # إعداد التنقل بالـ Enter
            self.setup_enter_navigation(selection_dialog)
            
            # عنوان النافذة
            ctk.CTkLabel(
                selection_dialog,
                text="👥 اختيار العملاء",
                font=("Arial", 16, "bold"),
                text_color="#25D366"
            ).pack(pady=10)
            
            # قائمة العملاء
            customers_frame = ctk.CTkFrame(selection_dialog, fg_color="#f0f0f0", corner_radius=8)
            customers_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
            
            # قائمة العملاء مع مربعات الاختيار
            self.customer_vars = {}
            for customer in customers:
                var = tk.BooleanVar()
                self.customer_vars[customer.id] = var
                
                ctk.CTkCheckBox(
                    customers_frame,
                    text=f"{customer.name} - {customer.phone}",
                    variable=var,
                    font=("Arial", 11)
                ).pack(anchor=tk.W, padx=10, pady=2)
            
            # أزرار التحكم
            buttons_frame = ctk.CTkFrame(selection_dialog, fg_color="transparent")
            buttons_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
            
            ctk.CTkButton(
                buttons_frame,
                text="📤 إرسال للمحددين",
                command=lambda: self.send_to_selected_customers(message, selection_dialog),
                fg_color="#25D366",
                hover_color="#128C7E",
                width=120
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            ctk.CTkButton(
                buttons_frame,
                text="✅ تحديد الكل",
                command=self.select_all_customers,
                fg_color="#4CAF50",
                hover_color="#45a049",
                width=120
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            ctk.CTkButton(
                buttons_frame,
                text="❌ إلغاء",
                command=selection_dialog.destroy,
                fg_color="#757575",
                hover_color="#616161",
                width=120
            ).pack(side=tk.LEFT, padx=(0, 10))
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في عرض قائمة العملاء: {str(e)}")
    
    def select_all_customers(self):
        """تحديد جميع العملاء"""
        for var in self.customer_vars.values():
            var.set(True)
    
    def send_to_selected_customers(self, message, dialog):
        """إرسال الرسالة للعملاء المحددين"""
        try:
            selected_customers = []
            for customer_id, var in self.customer_vars.items():
                if var.get():
                    selected_customers.append(customer_id)
            
            if not selected_customers:
                messagebox.showwarning("تحذير", "يرجى اختيار عميل واحد على الأقل")
                return
            
            if not messagebox.askyesno("تأكيد", f"هل تريد إرسال الرسالة لـ {len(selected_customers)} عميل؟"):
                return
            
            # جلب بيانات العملاء المحددين
            db = next(get_db())
            customers = db.query(Customer).filter(Customer.id.in_(selected_customers)).all()
            db.close()
            
            # إرسال الرسالة لكل عميل
            sent_count = 0
            for customer in customers:
                try:
                    phone = customer.phone.replace('+', '').replace(' ', '').replace('-', '')
                    if not phone.startswith('961'):
                        phone = '961' + phone.lstrip('0')
                    
                    whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
                    webbrowser.open(whatsapp_url)
                    sent_count += 1
                    
                    # تأخير قصير بين الرسائل
                    import time
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"خطأ في إرسال رسالة للعميل {customer.name}: {e}")
            
            dialog.destroy()
            messagebox.showinfo("نجح", f"تم فتح الواتساب لإرسال الرسالة لـ {sent_count} عميل")
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في إرسال الرسالة: {str(e)}")
    
    def load_broadcast_settings(self):
        """تحميل إعدادات الرسائل الجماعية"""
        try:
            if hasattr(self, 'maintenance_service'):
                # تحميل إعداد الإرسال التلقائي
                auto_send = self.maintenance_service.get_system_setting("whatsapp_auto_send", "true")
                self.auto_send_enabled.set(auto_send.lower() == "true")
                
                # تحميل تأخير الإرسال
                delay = self.maintenance_service.get_system_setting("whatsapp_send_delay", "5")
                self.send_delay_var.set(delay)
        except Exception as e:
            print(f"خطأ في تحميل إعدادات الرسائل الجماعية: {e}")
    
    def save_broadcast_settings(self):
        """حفظ إعدادات الرسائل الجماعية"""
        try:
            if hasattr(self, 'maintenance_service'):
                # حفظ إعداد الإرسال التلقائي
                self.maintenance_service.set_system_setting(
                    "whatsapp_auto_send",
                    str(self.auto_send_enabled.get()).lower(),
                    "تفعيل الإرسال التلقائي"
                )
                
                # حفظ تأخير الإرسال
                self.maintenance_service.set_system_setting(
                    "whatsapp_send_delay",
                    self.send_delay_var.get(),
                    "تأخير الإرسال بالثواني"
                )
                
                messagebox.showinfo("نجح", "تم حفظ الإعدادات بنجاح!")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حفظ الإعدادات: {str(e)}")
    
    def reset_broadcast_settings(self):
        """إعادة تعيين إعدادات الرسائل الجماعية"""
        try:
            self.auto_send_enabled.set(True)
            self.send_delay_var.set("5")
            messagebox.showinfo("نجح", "تم إعادة تعيين الإعدادات للقيم الافتراضية!")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في إعادة التعيين: {str(e)}")
    
    def show_currency_settings(self):
        """إظهار نافذة إعدادات العملة"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("إعدادات العملة - ADR ELECTRONICS")
        dialog.geometry("500x400")
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # محتوى النافذة
        main_container = ctk.CTkFrame(dialog, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # عنوان النافذة
        title_frame = ctk.CTkFrame(main_container, fg_color="#FF9800", corner_radius=10)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(
            title_frame, 
            text="💰 إعدادات العملة", 
            font=("Arial", 18, "bold"), 
            text_color="white"
        ).pack(pady=3)
        
        # إطار الإعدادات
        settings_frame = ctk.CTkScrollableFrame(main_container, fg_color="#fafafa", corner_radius=10)
        settings_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # العملة الحالية
        current_currency_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        current_currency_frame.pack(fill=tk.X, pady=(20, 15), padx=20)
        
        ctk.CTkLabel(
            current_currency_frame,
            text="العملة الحالية:",
            font=("Arial", 12, "bold"),
            text_color="#424242"
        ).pack(anchor=tk.W, pady=(0, 1))
        
        # متغيرات العملة - الدولار أولوية مع سعر صرف 90000
        currency_var = tk.StringVar(value="USD")
        exchange_rate_var = tk.StringVar(value="90000.0")
        
        # اختيار العملة
        currency_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        currency_frame.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        ctk.CTkLabel(
            currency_frame,
            text="اختر العملة:",
            font=("Arial", 12, "bold"),
            text_color="#424242"
        ).pack(anchor=tk.W, pady=(0, 1))
        
        # أزرار اختيار العملة
        currency_buttons_frame = ctk.CTkFrame(currency_frame, fg_color="transparent")
        currency_buttons_frame.pack(fill=tk.X, pady=(0, 1))
        
        # الدولار أولاً (أولوية)
        usd_btn = ctk.CTkRadioButton(
            currency_buttons_frame,
            text="🇺🇸 دولار أمريكي ($) - أولوية",
            variable=currency_var,
            value="USD",
            font=("Arial", 12, "bold"),
            fg_color="#4CAF50",
            hover_color="#45a049"
        )
        usd_btn.pack(side=tk.LEFT, padx=(0, 20))
        
        lbp_btn = ctk.CTkRadioButton(
            currency_buttons_frame,
            text="🇱🇧 ليرة لبنانية (ل.ل)",
            variable=currency_var,
            value="LBP",
            font=("Arial", 12)
        )
        lbp_btn.pack(side=tk.LEFT)
        
        # سعر الصرف
        exchange_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        exchange_frame.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        ctk.CTkLabel(
            exchange_frame,
            text="سعر الصرف (1 دولار = كم ليرة لبنانية):",
            font=("Arial", 12, "bold"),
            text_color="#424242"
        ).pack(anchor=tk.W, pady=(0, 1))
        
        exchange_entry = ctk.CTkEntry(
            exchange_frame,
            textvariable=exchange_rate_var,
            width=200,
            height=35,
            placeholder_text="مثال: 90000",
            font=("Arial", 12, "bold"),
            fg_color="#E8F5E8",
            border_color="#4CAF50"
        )
        exchange_entry.pack(anchor=tk.W, pady=(0, 1))
        
        # ملاحظة
        ctk.CTkLabel(
            exchange_frame,
            text="💡 ملاحظة: سعر الصرف يستخدم لتحويل الأسعار بين العملتين (قابل للتغيير)",
            font=("Arial", 10),
            text_color="#666666"
        ).pack(anchor=tk.W, pady=(5, 0))
        
        # أزرار التحكم
        buttons_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        # إضافة مساحة إضافية
        ctk.CTkLabel(buttons_frame, text="", height=10).pack()
        
        def save_currency_settings():
            """حفظ إعدادات العملة"""
            try:
                currency = currency_var.get()
                exchange_rate = float(exchange_rate_var.get())
                
                # حفظ الإعدادات في ملف config
                import config
                config.DEFAULT_CURRENCY = currency
                config.EXCHANGE_RATE = exchange_rate
                
                messagebox.showinfo("نجاح", f"تم حفظ إعدادات العملة بنجاح!\nالعملة: {currency}\nسعر الصرف: {exchange_rate}")
                dialog.destroy()
                
            except ValueError:
                messagebox.showerror("خطأ", "الرجاء إدخال سعر صرف صحيح")
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ أثناء الحفظ: {str(e)}")
        
        # زر الحفظ
        save_btn = ctk.CTkButton(
            buttons_frame,
            text="💾 حفظ الإعدادات",
            command=save_currency_settings,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=200,
            height=40,
            font=("Arial", 12, "bold")
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # زر الإلغاء
        cancel_btn = ctk.CTkButton(
            buttons_frame,
            text="❌ إلغاء",
            command=dialog.destroy,
            fg_color="#dc3545",
            hover_color="#c82333",
            width=150,
            height=40,
            font=("Arial", 12, "bold")
        )
        cancel_btn.pack(side=tk.LEFT, padx=(10, 0))
    
    def show_backup_window(self):
        """عرض نافذة النسخ الاحتياطي"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("💾 النسخ الاحتياطي - ADR ELECTRONICS")
        dialog.geometry("800x600")
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # مركز النافذة على الشاشة
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"800x600+{x}+{y}")
        
        # عنوان النافذة
        title_frame = ctk.CTkFrame(dialog, fg_color="#9C27B0", corner_radius=15)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkLabel(
            title_frame, 
            text="💾 النسخ الاحتياطي الشامل", 
            font=("Arial", 22, "bold"), 
            text_color="white"
        ).pack(pady=10)
        
        # محتوى النافذة
        content_frame = ctk.CTkScrollableFrame(dialog, fg_color="#fafafa", corner_radius=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # معلومات النسخ الاحتياطي
        info_frame = ctk.CTkFrame(content_frame, fg_color="#e3f2fd", corner_radius=10)
        info_frame.pack(fill=tk.X, pady=2, padx=10)
        
        ctk.CTkLabel(
            info_frame,
            text="📋 معلومات النسخ الاحتياطي:",
            font=("Arial", 16, "bold"),
            text_color="#1976d2"
        ).pack(anchor=tk.W, padx=15, pady=(1, 1))
        
        info_text = """
• 💾 نسخ احتياطي شامل لجميع ملفات النظام
• 🗄️ نسخ احتياطي كامل لقاعدة البيانات
• 📁 ضغط النسخة الاحتياطية في ملف ZIP
• 🔒 تشفير وحماية النسخة الاحتياطية
• 📊 معلومات مفصلة عن النظام
• ⏰ نسخ احتياطي تلقائي يومي
        """
        
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=("Arial", 12),
            text_color="#424242"
        ).pack(anchor=tk.W, padx=15, pady=(0, 1))
        
        # أزرار النسخ الاحتياطي
        buttons_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=10, padx=10)
        
        def create_backup():
            """إنشاء نسخة احتياطية"""
            try:
                from utils.backup_system import BackupSystem
                
                # إنشاء شريط تقدم
                progress_frame = ctk.CTkFrame(content_frame, fg_color="#f0f0f0", corner_radius=8)
                progress_frame.pack(fill=tk.X, pady=2, padx=10)
                
                ctk.CTkLabel(
                    progress_frame,
                    text="🔄 جاري إنشاء النسخة الاحتياطية...",
                    font=("Arial", 14, "bold"),
                    text_color="#1976d2"
                ).pack(pady=2)
                
                progress_bar = ctk.CTkProgressBar(progress_frame)
                progress_bar.pack(fill=tk.X, padx=20, pady=(0, 1))
                progress_bar.set(0.1)
                
                dialog.update()
                
                # إنشاء النسخة الاحتياطية
                backup_system = BackupSystem()
                result = backup_system.create_full_backup()
                
                progress_bar.set(1.0)
                dialog.update()
                
                if result["success"]:
                    # إخفاء شريط التقدم
                    progress_frame.destroy()
                    
                    # عرض رسالة النجاح
                    success_frame = ctk.CTkFrame(content_frame, fg_color="#e8f5e8", corner_radius=8)
                    success_frame.pack(fill=tk.X, pady=2, padx=10)
                    
                    ctk.CTkLabel(
                        success_frame,
                        text="✅ تم إنشاء النسخة الاحتياطية بنجاح!",
                        font=("Arial", 16, "bold"),
                        text_color="#2e7d32"
                    ).pack(pady=2)
                    
                    # معلومات النسخة الاحتياطية
                    backup_info = f"""
📁 مسار النسخة الاحتياطية: {result["backup_path"]}
📊 حجم النسخة الاحتياطية: {result["size"] / (1024*1024):.2f} MB
⏰ تاريخ الإنشاء: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    """
                    
                    ctk.CTkLabel(
                        success_frame,
                        text=backup_info,
                        font=("Arial", 12),
                        text_color="#424242"
                    ).pack(pady=(0, 1))
                    
                else:
                    # عرض رسالة الخطأ
                    error_frame = ctk.CTkFrame(content_frame, fg_color="#ffebee", corner_radius=8)
                    error_frame.pack(fill=tk.X, pady=2, padx=10)
                    
                    ctk.CTkLabel(
                        error_frame,
                        text="❌ فشل في إنشاء النسخة الاحتياطية",
                        font=("Arial", 16, "bold"),
                        text_color="#d32f2f"
                    ).pack(pady=2)
                    
                    ctk.CTkLabel(
                        error_frame,
                        text=f"الخطأ: {result.get('error', 'خطأ غير معروف')}",
                        font=("Arial", 12),
                        text_color="#666666"
                    ).pack(pady=(0, 1))
                
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ في إنشاء النسخة الاحتياطية: {str(e)}")
        
        # زر إنشاء نسخة احتياطية
        create_btn = ctk.CTkButton(
            buttons_frame,
            text="💾 إنشاء نسخة احتياطية",
            command=create_backup,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=200,
            height=50,
            font=("Arial", 14, "bold")
        )
        create_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # زر إغلاق
        close_btn = ctk.CTkButton(
            buttons_frame,
            text="❌ إغلاق",
            command=dialog.destroy,
            fg_color="#f44336",
            hover_color="#da190b",
            width=150,
            height=50,
            font=("Arial", 14, "bold")
        )
        close_btn.pack(side=tk.LEFT, padx=(10, 0))
    
    def load_data(self, silent=False, use_threading=True):
        """تحميل بيانات الطلبات (محسّن للأداء)
        
        Args:
            silent (bool): إذا كان True، لا تظهر رسائل الخطأ
            use_threading (bool): استخدام threading لتحميل البيانات في الخلفية
        """
        # استخدام threading لتحميل البيانات في الخلفية (أسرع)
        if use_threading and not silent:
            def load_in_background():
                try:
                    self._load_data_sync(silent=True)
                except Exception as e:
                    print(f"خطأ في تحميل البيانات في الخلفية: {e}")
            
            thread = threading.Thread(target=load_in_background, daemon=True)
            thread.start()
            return True
        
        return self._load_data_sync(silent)
    
    def _load_data_sync(self, silent=False):
        """تحميل البيانات بشكل متزامن (داخلي - محسّن)"""
        # منع التحميل المتزامن
        if hasattr(self, '_is_loading') and self._is_loading:
            return False
        self._is_loading = True
        
        try:
            # التحقق من cache أولاً
            import time
            current_time = time.time()
            cache_key = getattr(self, 'current_filter_status', None)
            
            cache_valid = (
                self._data_cache is not None and
                self._data_cache_time is not None and
                self._data_cache_key == cache_key and
                (current_time - self._data_cache_time) < self._data_cache_ttl
            )
            
            if cache_valid:
                try:
                    tree_empty = not hasattr(self, 'tree') or len(self.tree.get_children()) == 0
                except Exception:
                    tree_empty = True
                
                if tree_empty and self._data_cache:
                    rows = [self._format_job_row(job) for job in self._data_cache]
                    self._replace_tree_rows(rows)
                
                if not silent:
                    self.update_stats(force_refresh=False)
                
                self._last_load_time = current_time
                self._is_loading = False
                return True
            
            # جلب البيانات من الخدمة
            if not hasattr(self, 'maintenance_service'):
                if not silent:
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                self._is_loading = False
                return False
            
            current_status = getattr(self, 'current_filter_status', None)
            if current_status:
                success, message, jobs = self.maintenance_service.search_jobs(
                    status=current_status,
                    limit=10000  # عدد كبير لجلب جميع النتائج
                )
            else:
                success, message, jobs = self.maintenance_service.search_jobs(limit=10000)
            
            # حفظ في cache
            if success:
                self._data_cache = jobs
                self._data_cache_time = current_time
                self._data_cache_key = cache_key
            
            if success:
                rows = [self._format_job_row(job) for job in jobs]
                self._replace_tree_rows(rows)
                
                # تحديث وقت آخر تحميل
                self._last_load_time = current_time
                
                # تحديث الإحصائيات (استخدام cache لتسريع العملية)
                if not silent:
                    self.update_stats(force_refresh=False)
                
                self._is_loading = False
                return True
            else:
                if not silent:
                    messagebox.showerror("خطأ", f"فشل في تحميل البيانات: {message}")
                self._is_loading = False
                return False
                
        except Exception as e:
            if not silent:
                messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
            import traceback
            traceback.print_exc()
            self._is_loading = False
            return False
    
    def invalidate_data_cache(self):
        """تفريغ بيانات الـ cache لإجبار التحديث القادم على جلب البيانات من القاعدة"""
        self._data_cache = None
        self._data_cache_time = None
        self._data_cache_key = None
    
    def _normalize_status_value(self, status):
        """إرجاع الحالة كنص بسيط"""
        if hasattr(status, 'value'):
            return status.value
        if hasattr(status, 'name'):
            return status.name.lower()
        return status or ""
    
    def _format_job_row(self, job: Dict[str, Any]):
        """تحويل بيانات الطلب إلى صف جاهز للعرض في الجدول"""
        status_value = self._normalize_status_value(job.get('status'))
        arabic_status = self.translate_status_to_arabic(status_value)
        
        payment_status = job.get('payment_status', 'unpaid')
        payment_method = job.get('payment_method', '')
        if payment_status == 'paid':
            if payment_method == 'cash':
                payment_display = "💵 كاش"
            elif payment_method == 'wish_money':
                payment_display = "💳 Wish"
            else:
                payment_display = "✅ مدفوع"
        else:
            payment_display = "📝 دين"
        
        price_value = job.get('final_cost') or job.get('estimated_cost')
        price_display = f"{price_value:.2f} $" if price_value else "غير محدد"
        
        serial_number = job.get('serial_number') or 'غير محدد'
        received_at = job.get('received_at')
        delivered_at = job.get('delivered_at')
        received_str = received_at.strftime('%Y-%m-%d') if received_at and hasattr(received_at, 'strftime') else ''
        delivered_str = delivered_at.strftime('%Y-%m-%d') if delivered_at and hasattr(delivered_at, 'strftime') else ''
        
        return (
            "☐",
            job.get('id', ''),
            job.get('tracking_code', ''),
            job.get('customer_name', 'غير معروف'),
            job.get('customer_phone', '-'),
            job.get('device_type', 'غير محدد'),
            serial_number,
            arabic_status,
            price_display,
            payment_display,
            received_str,
            delivered_str
        )
    
    def _replace_tree_rows(self, rows):
        """استبدال كل صفوف الجدول بالبيانات المعطاة"""
        if not hasattr(self, 'tree'):
            return
        
        items = self.tree.get_children()
        if items:
            self.tree.delete(*items)
        
        self.tree.config(displaycolumns='#all')
        for values in rows:
            self.tree.insert("", tk.END, values=values)
        self.tree.update_idletasks()
        self.tree.heading("select", text="☐")
        self._update_tree_count(len(rows))
    
    def _append_tree_row(self, job, prepend=False):
        """إضافة صف جديد إلى الجدول"""
        if not hasattr(self, 'tree'):
            return
        
        values = self._format_job_row(job)
        if prepend:
            self.tree.insert("", 0, values=values)
        else:
            self.tree.insert("", tk.END, values=values)
        self.tree.update_idletasks()
        self._update_tree_count()
    
    def _update_tree_count(self, count=None):
        """تحديث عداد العناصر المعروضة"""
        if not hasattr(self, 'status_count'):
            return
        
        if count is None:
            if hasattr(self, 'tree'):
                count = len(self.tree.get_children())
            else:
                count = 0
        
        current_status = getattr(self, 'current_filter_status', None)
        if current_status:
            status_label = self.translate_status_to_arabic(current_status)
            text = f"{self.format_number_english(count)} عنصر ({status_label})"
        else:
            text = f"{self.format_number_english(count)} عنصر"
        self.status_count.configure(text=text)
    
    def _job_matches_current_filter(self, status_value):
        """التحقق مما إذا كان الطلب يطابق الفلتر الحالي"""
        current_status = getattr(self, 'current_filter_status', None)
        if not current_status:
            return True
        normalized = self._normalize_status_value(status_value)
        return normalized == current_status
    
    def _insert_new_job_fast(self, job_data, customer_name, phone, device_type, serial, estimated_cost_value):
        """إضافة صف جديد مباشرة بعد حفظ الطلب بدون إعادة تحميل كاملة"""
        try:
            job_summary = {
                "id": job_data.get('id'),
                "tracking_code": job_data.get('tracking_code'),
                "customer_name": customer_name,
                "customer_phone": phone or "غير معروف",
                "device_type": device_type or "غير محدد",
                "serial_number": serial or "غير محدد",
                "status": self._normalize_status_value(job_data.get('status')),
                "received_at": job_data.get('received_at'),
                "delivered_at": None,
                "estimated_cost": estimated_cost_value,
                "final_cost": None,
                "payment_status": "paid",
                "payment_method": "cash"
            }
            
            if self._job_matches_current_filter(job_summary["status"]):
                self._append_tree_row(job_summary, prepend=True)
        except Exception as exc:
            print(f"⚠️ فشل في التحديث السريع لقائمة الطلبات: {exc}")
    
    def update_stats(self, force_refresh=False):
        """تحديث إحصائيات الطلبات مع cache"""
        try:
            # التحقق من وجود stats_cards
            if not hasattr(self, 'stats_cards'):
                print("⚠️ تحذير: stats_cards غير موجود - سيتم تجاوز التحديث")
                return False
            
            if not self.stats_cards:
                print("⚠️ تحذير: stats_cards فارغ - سيتم تجاوز التحديث")
                return False
            
            # جلب إحصائيات الطلبات
            if not hasattr(self, 'maintenance_service'):
                print("⚠️ تحذير: maintenance_service غير موجود - سيتم تجاوز التحديث")
                return False
            
            print("🔄 بدء تحديث الإحصائيات...")
            
            # استخدام cache إذا كان متاحاً وغير منتهي الصلاحية
            import time
            current_time = time.time()
            if (not force_refresh and 
                hasattr(self, '_stats_cache') and 
                self._stats_cache is not None and 
                hasattr(self, '_stats_cache_time') and 
                self._stats_cache_time is not None and
                (current_time - self._stats_cache_time) < self._cache_ttl):
                stats = self._stats_cache
                success = True
                message = "تم جلب الإحصائيات من cache"
            else:
                print("🔄 جلب الإحصائيات من قاعدة البيانات...")
                success, message, stats = self.maintenance_service.get_dashboard_stats()
                print(f"📊 نتيجة جلب الإحصائيات: success={success}, message={message}")
                if success:
                    print(f"📊 البيانات المستلمة: {stats}")
                    # حفظ في cache
                    self._stats_cache = stats
                    self._stats_cache_time = current_time
                else:
                    print(f"❌ فشل في جلب الإحصائيات: {message}")
            
            if success:
                # التحقق من صحة البيانات
                total_jobs = stats.get('total_jobs', 0)
                in_progress = stats.get('in_progress', 0)
                ready_for_delivery = stats.get('ready_for_delivery', 0)
                delivered = stats.get('delivered', 0)
                
                # التحقق من أن الأرقام منطقية
                calculated_total = in_progress + ready_for_delivery + delivered
                if calculated_total != total_jobs:
                    print(f"⚠️ تحذير: مجموع الإحصائيات ({calculated_total}) لا يطابق إجمالي الطلبات ({total_jobs})")
                    print(f"   التفاصيل: قيد المعالجة={in_progress}, جاهزة={ready_for_delivery}, مسلمة={delivered}")
                
                # تحديث البطاقات الإحصائية
                print(f"🔄 تحديث البطاقات الإحصائية...")
                print(f"   - إجمالي الطلبات: {total_jobs}")
                print(f"   - قيد المعالجة: {in_progress}")
                print(f"   - جاهزة للتسليم: {ready_for_delivery}")
                print(f"   - تم التسليم: {delivered}")
                
                if 'total_jobs' in stats:
                    formatted_total = self.format_number_english(total_jobs)
                    print(f"🔄 تحديث بطاقة 'إجمالي الطلبات' بالقيمة: {formatted_total}")
                    self.update_stat_card("إجمالي الطلبات", formatted_total)
                if 'in_progress' in stats:
                    formatted_in_progress = self.format_number_english(in_progress)
                    print(f"🔄 تحديث بطاقة 'قيد المعالجة' بالقيمة: {formatted_in_progress}")
                    self.update_stat_card("قيد المعالجة", formatted_in_progress)
                if 'ready_for_delivery' in stats:
                    formatted_ready = self.format_number_english(ready_for_delivery)
                    print(f"🔄 تحديث بطاقة 'جاهزة للتسليم' بالقيمة: {formatted_ready}")
                    self.update_stat_card("جاهزة للتسليم", formatted_ready)
                if 'delivered' in stats:
                    formatted_delivered = self.format_number_english(delivered)
                    print(f"🔄 تحديث بطاقة 'تم التسليم' بالقيمة: {formatted_delivered}")
                    
                    # إضافة تاريخ آخر تسليم إذا كان متوفراً
                    delivery_date_info = None
                    if 'last_delivery_date' in stats and stats['last_delivery_date']:
                        try:
                            if isinstance(stats['last_delivery_date'], datetime):
                                delivery_date_info = f"آخر تسليم: {stats['last_delivery_date'].strftime('%Y-%m-%d')}"
                            else:
                                delivery_date_info = f"آخر تسليم: {str(stats['last_delivery_date'])[:10]}"
                        except Exception as e:
                            print(f"⚠️ خطأ في تنسيق تاريخ التسليم: {e}")
                    
                    self.update_stat_card("تم التسليم", formatted_delivered, delivery_date_info)
                
                print(f"✅ تم تحديث الإحصائيات بنجاح: إجمالي={total_jobs}, قيد المعالجة={in_progress}, جاهزة={ready_for_delivery}, مسلمة={delivered}")
                return True
            else:
                print(f"❌ فشل في جلب الإحصائيات: {message}")
                if hasattr(self, 'status_label'):
                    self.status_label.configure(text=f"خطأ في تحميل الإحصائيات: {message}")
                return False
                
        except Exception as e:
            print(f"❌ خطأ في تحديث الإحصائيات: {e}")
            import traceback
            traceback.print_exc()
            if hasattr(self, 'status_label'):
                self.status_label.configure(text=f"خطأ في تحديث الإحصائيات: {str(e)}")
            return False
    
    def update_stat_card(self, title, value, extra_info=None):
        """تحديث قيمة بطاقة إحصائية"""
        try:
            if not hasattr(self, 'stats_cards'):
                print(f"⚠️ تحذير: stats_cards غير موجود عند محاولة تحديث '{title}'")
                return
                
            if title not in self.stats_cards:
                print(f"⚠️ تحذير: '{title}' غير موجود في stats_cards")
                print(f"   البطاقات المتاحة: {list(self.stats_cards.keys())}")
                return
            
            print(f"🔄 تحديث بطاقة '{title}' بالقيمة '{value}'")
            
            # الحصول على الإطار الأصلي
            card = self.stats_cards[title]
            
            # تحديد حالة الفلترة لكل بطاقة
            filter_status = None
            if title == "إجمالي الطلبات":
                filter_status = None
            elif title == "قيد المعالجة":
                filter_status = "received"
            elif title == "جاهزة للتسليم":
                filter_status = "repaired"
            elif title == "تم التسليم":
                filter_status = "delivered"
            
            # تدمير العناصر الحالية
            for widget in card.winfo_children():
                widget.destroy()
            
            # إضافة القيمة الجديدة مع الأحداث
            value_label = ctk.CTkLabel(
                card, 
                text=str(value), 
                font=("Arial", 24, "bold"),
                text_color="white",
                cursor="hand2"
            )
            value_label.pack(padx=20, pady=(15, 5))
            value_label.bind("<Button-1>", lambda e, status=filter_status: self.filter_by_status_from_stats(status))
            
            title_label = ctk.CTkLabel(
                card, 
                text=title,
                text_color="white",
                cursor="hand2"
            )
            title_label.pack(padx=20, pady=(0, 1))
            title_label.bind("<Button-1>", lambda e, status=filter_status: self.filter_by_status_from_stats(status))
            
            # إضافة معلومات إضافية (مثل تاريخ التسليم)
            if extra_info:
                extra_label = ctk.CTkLabel(
                    card,
                    text=extra_info,
                    text_color="white",
                    font=("Arial", 10),
                    cursor="hand2"
                )
                extra_label.pack(padx=20, pady=(0, 10))
                extra_label.bind("<Button-1>", lambda e, status=filter_status: self.filter_by_status_from_stats(status))
            
            # إعادة ربط حدث النقر على البطاقة نفسها
            card.bind("<Button-1>", lambda e, status=filter_status: self.filter_by_status_from_stats(status))
            
        except Exception as e:
            print(f"خطأ في تحديث بطاقة الإحصائية: {e}")
            import traceback
            traceback.print_exc()
    
    
    def _search_device(self, code, customer_entry=None, device_type_entry=None, model_entry=None, serial_entry=None, barcode_entry=None):
        """البحث عن جهاز باستخدام الباركود أو الرقم التسلسلي"""
        if not code:
            return
            
        # البحث في قاعدة البيانات
        if not hasattr(self, 'code_service'):
            return None
        device = self.code_service.find_device_by_code(code)
        
        if device:
            # تعبئة الحقول ببيانات الجهاز إذا تم توفيرها
            if customer_entry:
                customer_entry.delete(0, tk.END)
                customer_entry.insert("0", device.get('customer_name', ''))
            
            if device_type_entry:
                device_type_entry.delete(0, tk.END)
                device_type_entry.insert("0", device.get('device_type', ''))
                
            if model_entry:
                model_entry.delete(0, tk.END)
                model_entry.insert("0", device.get('device_model', ''))
                
            if serial_entry:
                serial_entry.delete(0, tk.END)
                serial_entry.insert("0", device.get('device_serial', ''))
            
            # عرض رسالة للتنبيه بأنه تم العثور على الجهاز
            messagebox.showinfo(
                "تم العثور على الجهاز",
                f"تم العثور على جهاز مسجل مسبقاً\n"
                f"النوع: {device.get('device_type', 'غير محدد')}\n"
                f"الموديل: {device.get('device_model', 'غير محدد')}"
            )
            return device
        
        return None

    def _search_device_history(self, code):
        """البحث عن تاريخ الجهاز بالباركود أو الرقم التسلسلي"""
        try:
            if not hasattr(self, 'maintenance_service'):
                return None
            
            db = next(get_db())
            from database.models import MaintenanceJob, Customer, Customer, StatusHistory
            
            # البحث عن جميع طلبات الصيانة لهذا الجهاز
            jobs = db.query(MaintenanceJob).filter(
                (MaintenanceJob.serial_number == code) | 
                (MaintenanceJob.tracking_code == code)
            ).order_by(MaintenanceJob.received_at.desc()).all()
            
            if not jobs:
                db.close()
                return None
            
            # تجميع تاريخ الجهاز
            device_history = {
                'serial_number': code,
                'total_jobs': len(jobs),
                'jobs': []
            }
            
            for job in jobs:
                # الحصول على تاريخ الحالات
                status_history = db.query(StatusHistory).filter_by(maintenance_job_id=job.id).order_by(StatusHistory.created_at).all()
                
                job_info = {
                    'id': job.id,
                    'tracking_code': job.tracking_code,
                    'customer_name': job.customer.name,
                    'device_type': job.device_type,
                    'received_at': job.received_at,
                    'completed_at': job.completed_at,
                    'current_status': job.status,
                    'status_history': [
                        {
                            'status': status.status,
                            'created_at': status.created_at,
                            'notes': status.notes
                        } for status in status_history
                    ]
                }
                device_history['jobs'].append(job_info)
            
            db.close()
            return device_history
            
        except Exception as e:
            print(f"خطأ في البحث عن تاريخ الجهاز: {str(e)}")
            return None
    
    def show_device_history_dialog(self, device_history, customer_entry, device_type_entry, serial_entry, barcode_entry):
        """عرض نافذة تاريخ الجهاز"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"تاريخ الجهاز - {device_history['serial_number']}")
        dialog.geometry("800x600")
        dialog.grab_set()
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # عنوان النافذة
        title_frame = ctk.CTkFrame(dialog, fg_color="#1976d2", corner_radius=10)
        title_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            title_frame, 
            text=f"تاريخ الجهاز: {device_history['serial_number']}", 
            font=("Arial", 16, "bold"), 
            text_color="white"
        ).pack(pady=3)
        
        ctk.CTkLabel(
            title_frame, 
            text=f"إجمالي الطلبات: {device_history['total_jobs']}", 
            font=("Arial", 12), 
            text_color="white"
        ).pack(pady=(0, 1))
        
        # إطار المحتوى
        content_frame = ctk.CTkScrollableFrame(dialog, fg_color="#fafafa", corner_radius=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # عرض كل طلب
        for i, job in enumerate(device_history['jobs']):
            job_frame = ctk.CTkFrame(content_frame, fg_color="#e3f2fd", corner_radius=8)
            job_frame.pack(fill=tk.X, pady=(0, 1), padx=10)
            
            # معلومات الطلب الأساسية
            info_frame = ctk.CTkFrame(job_frame, fg_color="transparent")
            info_frame.pack(fill=tk.X, pady=2, padx=15)
            
            ctk.CTkLabel(
                info_frame, 
                text=f"طلب #{i+1}: {job['tracking_code']}", 
                font=("Arial", 14, "bold"),
                text_color="#1976d2"
            ).pack(anchor=tk.W, pady=(0, 1))
            
            ctk.CTkLabel(
                info_frame, 
                text=f"العميل: {job['customer_name']}", 
                font=("Arial", 12),
                text_color="#424242"
            ).pack(anchor=tk.W, pady=(0, 1))
            
            ctk.CTkLabel(
                info_frame, 
                text=f"نوع الجهاز: {job['device_type']}", 
                font=("Arial", 12),
                text_color="#424242"
            ).pack(anchor=tk.W, pady=(0, 1))
            
            ctk.CTkLabel(
                info_frame, 
                text=f"تاريخ الاستلام: {job['received_at'].strftime('%Y-%m-%d %H:%M') if job['received_at'] else 'غير محدد'}", 
                font=("Arial", 12),
                text_color="#424242"
            ).pack(anchor=tk.W, pady=(0, 1))
            
            # ترجمة الحالة إلى العربية
            current_status = job['current_status']
            if hasattr(current_status, 'value'):
                status_value = current_status.value
            else:
                status_value = str(current_status)
            arabic_status = self.translate_status_to_arabic(status_value)
            
            ctk.CTkLabel(
                info_frame, 
                text=f"الحالة الحالية: {arabic_status}", 
                font=("Arial", 12, "bold"),
                text_color="#2e7d32"
            ).pack(anchor=tk.W, pady=(0, 1))
            
            # تاريخ الحالات
            if job['status_history']:
                ctk.CTkLabel(
                    info_frame, 
                    text="تاريخ الحالات:", 
                    font=("Arial", 12, "bold"),
                    text_color="#f57c00"
                ).pack(anchor=tk.W, pady=(0, 1))
                
                for status in job['status_history']:
                    # ترجمة الحالة إلى العربية
                    status_value = status['status']
                    if hasattr(status_value, 'value'):
                        status_value = status_value.value
                    else:
                        status_value = str(status_value)
                    arabic_status = self.translate_status_to_arabic(status_value)
                    
                    status_text = f"• {arabic_status} - {status['created_at'].strftime('%Y-%m-%d %H:%M')}"
                    if status['notes']:
                        status_text += f" ({status['notes']})"
                    
                    ctk.CTkLabel(
                        info_frame, 
                        text=status_text, 
                        font=("Arial", 10),
                        text_color="#666666"
                    ).pack(anchor=tk.W, pady=(0, 1), padx=20)
        
        # أزرار
        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        def use_this_device():
            # استخدام بيانات آخر طلب
            if device_history['jobs']:
                last_job = device_history['jobs'][0]  # أحدث طلب
                
                # تعبئة الحقول
                customer_entry.delete(0, tk.END)
                customer_entry.insert("0", last_job['customer_name'])
                
                device_type_entry.delete(0, tk.END)
                device_type_entry.insert("0", last_job['device_type'])
                
                serial_entry.delete(0, tk.END)
                serial_entry.insert("0", device_history['serial_number'])
                
                barcode_entry.delete(0, tk.END)
                barcode_entry.insert("0", device_history['serial_number'])
            
            dialog.destroy()
        
        ctk.CTkButton(
            button_frame, 
            text="استخدام هذا الجهاز", 
            command=use_this_device,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=200,
            height=40,
            font=("Arial", 12, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ctk.CTkButton(
            button_frame, 
            text="إغلاق", 
            command=dialog.destroy,
            fg_color="#f44336",
            hover_color="#da190b",
            width=150,
            height=40,
            font=("Arial", 12, "bold")
        ).pack(side=tk.LEFT, padx=(10, 0))
    def add_maintenance_old(self):
        """إضافة طلب صيانة جديد - قديم"""
        # إنشاء نافذة الإضافة
        dialog = ctk.CTkToplevel(self)
        dialog.title("إضافة طلب صيانة جديد - ADR ELECTRONICS")
        dialog.geometry("500x800")  # نافذة أطول وأضيق
        dialog.grab_set()  # جعل النافذة مركزة
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # توليد كود جديد فوراً عند فتح النافذة من قاعدة البيانات
        if hasattr(self, 'maintenance_service'):
            current_code = self.maintenance_service.generate_tracking_code()
        else:
            current_code = "A1"
        
        # متغير لحفظ الكود المولد
        generated_code = tk.StringVar()
        generated_code.set(current_code)  # استخدام الكود المولد
        
        # محتوى النافذة الرئيسي
        main_container = ctk.CTkFrame(dialog, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # عنوان النافذة
        title_frame = ctk.CTkFrame(main_container, fg_color="#1976d2", corner_radius=10)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(
            title_frame, 
            text="إضافة طلب صيانة جديد", 
            font=("Arial", 18, "bold"), 
            text_color="white"
        ).pack(pady=3)
        
        # عرض الكود المرجعي مع تحديث تلقائي
        code_section = ctk.CTkFrame(main_container, fg_color="#e8f5e8", corner_radius=8, border_width=2, border_color="#4caf50")
        code_section.pack(fill=tk.X, pady=(0, 20))
        
        ctk.CTkLabel(
            code_section, 
            text="🏷️ الكود المرجعي للجهاز الجديد", 
            font=("Arial", 14, "bold"), 
            text_color="#2e7d32"
        ).pack(anchor=tk.W, pady=(5, 3), padx=15)
        
        ctk.CTkLabel(
            code_section, 
            text="يجب تسجيل هذا الكود على الجهاز:", 
            font=("Arial", 11), 
            text_color="#4caf50"
        ).pack(anchor=tk.W, pady=(0, 1), padx=15)
        
        code_display = ctk.CTkLabel(
            code_section,
            textvariable=generated_code,
            font=("Arial", 20, "bold"),
            text_color="#1b5e20",
            fg_color="#c8e6c9",
            corner_radius=8,
            width=200,
            height=40
        )
        code_display.pack(pady=(0, 1))
        
        # تحديث الكود في النافذة فوراً
        generated_code.set(current_code)
        code_display.configure(text=current_code)
        
        # إطار النموذج الرئيسي
        form_container = ctk.CTkScrollableFrame(main_container, fg_color="#fafafa", corner_radius=10)
        form_container.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # حقل الباركود
        barcode_section = ctk.CTkFrame(form_container, fg_color="transparent")
        barcode_section.pack(fill=tk.X, pady=(0, 1))
        
        ctk.CTkLabel(
            barcode_section, 
            text="باركود/رقم تسلسلي", 
            font=("Arial", 12, "bold"),
            text_color="#424242"
        ).pack(anchor=tk.W, pady=(0, 1))
        
        barcode_entry = ctk.CTkEntry(
            barcode_section, 
            width=400, 
            height=35,
            placeholder_text="ادخل الباركود أو اتركه فارغاً ليتم توليد الكود الحالي",
            font=("Arial", 12)
        )
        barcode_entry.pack(fill=tk.X, pady=(0, 1))
        
        # دالة لتوليد الكود الحالي إذا كان حقل الباركود فارغاً
        def on_barcode_leave(event):
            if not barcode_entry.get().strip():
                barcode_entry.delete(0, tk.END)
                barcode_entry.insert("0", generated_code.get())
        
        # حقل الباركود يبقى فارغاً عند فتح النافذة
        
        barcode_entry.bind('<FocusOut>', on_barcode_leave)
        
        # قسم معلومات العميل
        customer_section = ctk.CTkFrame(form_container, fg_color="#e3f2fd", corner_radius=8)
        customer_section.pack(fill=tk.X, pady=(0, 1))
        
        ctk.CTkLabel(
            customer_section, 
            text="معلومات العميل", 
            font=("Arial", 14, "bold"),
            text_color="#1976d2"
        ).pack(anchor=tk.W, pady=(1, 1), padx=15)
        
        # حقل اسم العميل
        name_frame = ctk.CTkFrame(customer_section, fg_color="transparent")
        name_frame.pack(fill=tk.X, pady=(0, 1), padx=15)
        
        ctk.CTkLabel(
            name_frame, 
            text="اسم العميل *", 
            font=("Arial", 12, "bold"), 
            text_color="#d32f2f"
        ).pack(anchor=tk.W, pady=(0, 1))
        
        customer_entry = ctk.CTkEntry(
            name_frame, 
            width=400, 
            height=35,
            placeholder_text="أدخل اسم العميل",
            font=("Arial", 12)
        )
        customer_entry.pack(fill=tk.X, pady=(0, 1))
        customer_entry.bind('<Return>', lambda e: phone_entry.focus())
        customer_entry.bind('<KeyPress-Return>', lambda e: phone_entry.focus())
        
        # حقل رقم الهاتف مع إشارة بصرية
        phone_frame = ctk.CTkFrame(customer_section, fg_color="transparent")
        phone_frame.pack(fill=tk.X, pady=(0, 1), padx=15)
        
        # إطار العنوان مع إشارة الحالة
        phone_title_frame = ctk.CTkFrame(phone_frame, fg_color="transparent")
        phone_title_frame.pack(fill=tk.X, pady=(0, 1))
        
        ctk.CTkLabel(
            phone_title_frame, 
            text="رقم الهاتف *", 
            font=("Arial", 12, "bold"), 
            text_color="#d32f2f"
        ).pack(side=tk.LEFT)
        
        # إشارة بصرية للحالة (ستظهر عند العثور على العميل)
        status_label = ctk.CTkLabel(
            phone_title_frame, 
            text="", 
            font=("Arial", 10, "bold"),
            text_color="#4caf50"
        )
        status_label.pack(side=tk.RIGHT)
        
        phone_entry = ctk.CTkEntry(
            phone_frame, 
            width=400, 
            height=35,
            placeholder_text="أدخل رقم الهاتف",
            font=("Arial", 12)
        )
        phone_entry.pack(fill=tk.X, pady=(0, 1))
        phone_entry.bind('<Return>', lambda e: device_type_entry.focus())
        phone_entry.bind('<KeyPress-Return>', lambda e: device_type_entry.focus())
        
        # دالة للبحث عن العميل وملء رقم الهاتف تلقائياً (بدون نافذة منبثقة)
        def search_customer_by_name(event=None):
            customer_name = customer_entry.get().strip()
            if customer_name and hasattr(self, 'maintenance_service'):
                try:
                    # البحث عن العميل في قاعدة البيانات (بحث دقيق بالاسم الكامل)
                    db = next(get_db())
                    from database.models import Customer
                    customer = db.query(Customer).filter(Customer.name.ilike(f"%{customer_name}%")).first()
                    db.close()
                    
                    if customer:
                        # ملء رقم الهاتف تلقائياً بدون رسالة
                        phone_entry.delete(0, tk.END)
                        phone_entry.insert("0", customer.phone)
                        
                        # تغيير لون حقل الهاتف للإشارة إلى أنه تم ملؤه تلقائياً
                        phone_entry.configure(fg_color="#e8f5e8", border_color="#4caf50")
                        
                        # وضع الكود في حقل الباركود عند العثور على العميل
                        barcode_entry.delete(0, tk.END)
                        barcode_entry.insert("0", generated_code.get())
                        
                        # إظهار إشارة بصرية
                        status_label.configure(text="✓ تم العثور على العميل")
                        status_label.configure(text_color="#4caf50")
                    else:
                        # إعادة تعيين لون حقل الهاتف
                        phone_entry.configure(fg_color=("gray95", "gray10"), border_color=("gray60", "gray30"))
                        phone_entry.configure(placeholder_text="أدخل رقم الهاتف")
                        
                        # إخفاء الإشارة البصرية
                        status_label.configure(text="")
                except Exception as e:
                    print(f"خطأ في البحث عن العميل: {str(e)}")
        
        # ربط البحث عند ترك حقل اسم العميل (FocusOut) بدلاً من KeyRelease
        customer_entry.bind('<FocusOut>', search_customer_by_name)
        customer_entry.bind('<Return>', lambda e: phone_entry.focus())
        phone_entry.bind('<Return>', lambda e: device_type_entry.focus())
        
        # قسم معلومات الجهاز
        device_section = ctk.CTkFrame(form_container, fg_color="#fff3e0", corner_radius=8)
        device_section.pack(fill=tk.X, pady=(0, 1))
        
        ctk.CTkLabel(
            device_section, 
            text="معلومات الجهاز", 
            font=("Arial", 14, "bold"),
            text_color="#f57c00"
        ).pack(anchor=tk.W, pady=(1, 1), padx=15)
        
        # حقل نوع الجهاز
        device_type_frame = ctk.CTkFrame(device_section, fg_color="transparent")
        device_type_frame.pack(fill=tk.X, pady=(0, 1), padx=15)
        
        ctk.CTkLabel(
            device_type_frame, 
            text="نوع الجهاز *", 
            font=("Arial", 12, "bold"), 
            text_color="#d32f2f"
        ).pack(anchor=tk.W, pady=(0, 1))
        
        device_type_entry = ctk.CTkEntry(
            device_type_frame, 
            width=400, 
            height=35,
            placeholder_text="مثال: هاتف محمول، حاسوب محمول، تابلت",
            font=("Arial", 12)
        )
        device_type_entry.pack(fill=tk.X, pady=(0, 1))
        device_type_entry.bind('<Return>', lambda e: issue_text.focus())
        device_type_entry.bind('<KeyPress-Return>', lambda e: issue_text.focus())
        
        # حقل وصف العطل
        issue_section = ctk.CTkFrame(form_container, fg_color="#f3e5f5", corner_radius=8)
        issue_section.pack(fill=tk.X, pady=(0, 1))
        
        ctk.CTkLabel(
            issue_section, 
            text="وصف العطل", 
            font=("Arial", 14, "bold"),
            text_color="#7b1fa2"
        ).pack(anchor=tk.W, pady=(5, 3), padx=15)
        
        issue_text = ctk.CTkTextbox(
            issue_section, 
            height=30,
            font=("Arial", 12)
        )
        issue_text.pack(fill=tk.X, pady=(0, 1), padx=15)
        def save_on_issue_enter(event):
            """حفظ الطلب عند الضغط على Enter داخل خانة وصف العطل."""
            try:
                if event.state & 0x0001:  # Shift لتعديل السطر
                    return
            except Exception:
                pass
            save()
            return "break"
        
        issue_text.bind('<Return>', save_on_issue_enter)
        issue_text.bind('<KeyPress-Return>', save_on_issue_enter)
        
        # إضافة نص توضيحي
        issue_text.insert("1.0", "وصف العطل أو المشكلة في الجهاز")
        issue_text.configure(text_color="gray")
        
        # دالة لمسح النص التوضيحي
        def clear_placeholder(event):
            if issue_text.get("1.0", tk.END).strip() == "وصف العطل أو المشكلة في الجهاز":
                issue_text.delete("1.0", tk.END)
                issue_text.configure(text_color="black")
        
        issue_text.bind("<FocusIn>", clear_placeholder)
        
        # أزرار الحفظ والإلغاء - تصميم احترافي
        button_section = ctk.CTkFrame(main_container, fg_color="transparent")
        button_section.pack(fill=tk.X, pady=(0, 1))
        
        # إطار الأزرار
        buttons_container = ctk.CTkFrame(button_section, fg_color="transparent")
        buttons_container.pack(fill=tk.X, pady=2)
        
        def save():
            # جمع البيانات من جميع الحقول
            customer_name = customer_entry.get().strip()
            phone = phone_entry.get().strip()
            device_type = device_type_entry.get().strip()
            barcode = barcode_entry.get().strip()
            issue = issue_text.get("1.0", tk.END).strip()
            
            # التحقق من البيانات المطلوبة
            required_fields = []
            if not customer_name:
                required_fields.append("اسم العميل")
            if not phone:
                required_fields.append("رقم الهاتف")
            if not device_type:
                required_fields.append("نوع الجهاز")
                
            if required_fields:
                messagebox.showwarning("حقول مطلوبة", f"الرجاء إدخال الحقول التالية:\n{', '.join(required_fields)}")
                return
            
            try:
                # استخدام الباركود إذا كان موجوداً، وإلا استخدم الكود المرجعي
                final_serial = barcode if barcode else generated_code.get()
                
                # إذا لم يكن هناك باركود، استخدم الكود المولد كباركود
                if not barcode:
                    barcode_entry.delete(0, tk.END)
                    barcode_entry.insert(0, final_serial)
                
                # حفظ البيانات
                if not hasattr(self, 'maintenance_service'):
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    return
                    
                # استخراج نوع الكود من القائمة المنسدلة
                selected_type = code_type_var.get()
                code_letter = selected_type.split(" - ")[0] if " - " in selected_type else selected_type
                
                
                success, message, job = self.maintenance_service.create_maintenance_job(
                    customer_name=customer_name,
                    phone=phone,
                    device_type=device_type,
                    device_model=None,
                    serial_number=final_serial,
                    issue_description=issue if issue and issue != "وصف العطل أو المشكلة في الجهاز" else "لم يتم تحديد وصف العطل",
                    code_type=code_letter
                )
                
                if success:
                    # حفظ بيانات الجهاز في سجل الأكواد لميزات البحث المستقبلية
                    if hasattr(self, 'code_service'):
                        try:
                            device_data = {
                                'serial_number': final_serial,
                                'barcode': final_serial,
                                'device_type': device_type,
                                'device_model': None,
                                'customer_name': customer_name
                            }
                            self.code_service.save_device_code(device_data)
                        except Exception as save_error:
                            print(f"⚠️ تحذير: تعذر حفظ بيانات الجهاز في سجل الأكواد: {save_error}")
                    
                    # تحديث الكود المرجعي للطلب التالي
                    if hasattr(self, 'code_service'):
                        new_code = self.code_service.generate_unique_code()
                        generated_code.set(new_code)
                        code_display.configure(text=new_code)
                        
                        # مسح الحقول للطلب التالي
                        customer_entry.delete(0, tk.END)
                        phone_entry.delete(0, tk.END)
                        device_type_entry.delete(0, tk.END)
                        barcode_entry.delete(0, tk.END)
                        issue_text.delete("1.0", tk.END)
                        issue_text.insert("1.0", "وصف العطل أو المشكلة في الجهاز")
                        issue_text.configure(text_color="gray")
                        
                        # إعادة تعيين لون حقل الهاتف
                        phone_entry.configure(fg_color=("gray95", "gray10"), border_color=("gray60", "gray30"))
                        phone_entry.configure(placeholder_text="أدخل رقم الهاتف")
                        status_label.configure(text="")
                    
                    # حفظ بيانات العميل الأخير
                    self.last_customer_name = customer_name
                    self.last_customer_phone = phone
                    
                    messagebox.showinfo("نجاح", f"تم إضافة طلب الصيانة بنجاح\nرقم التتبع: {job['tracking_code']}\nالكود الجديد: {generated_code.get()}")
                    self.load_data()  # تحديث الجدول
                    
                    # لا نغلق النافذة، نتركها مفتوحة للطلب التالي
                else:
                    messagebox.showerror("خطأ", f"فشل في حفظ البيانات: {message}")
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
        
        # زر الحفظ مع تنسيق محسن
        def trigger_save_from_button(event=None):
            save()
            return "break"
        
        save_btn = ctk.CTkButton(
            buttons_container, 
            text="💾 حفظ الطلب", 
            command=save,
            fg_color="#28a745",  # لون أخضر
            hover_color="#218838",
            width=180,
            height=45,
            font=("Arial", 13, "bold"),
            corner_radius=10
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # زر حفظ في الهاتف
        def save_to_phone():
            """حفظ العميل الأخير في جهات اتصال الهاتف"""
            if hasattr(self, 'last_customer_name') and hasattr(self, 'last_customer_phone'):
                self.show_contact_save_options(self.last_customer_name, self.last_customer_phone)
            else:
                # إذا لم يتم حفظ طلب بعد، استخدم البيانات من الحقول
                name = customer_entry.get().strip()
                phone_val = phone_entry.get().strip()
                if name and phone_val:
                    self.show_contact_save_options(name, phone_val)
                else:
                    messagebox.showwarning("تنبيه", "الرجاء حفظ الطلب أولاً أو إدخال اسم ورقم الهاتف")
        
        phone_btn = ctk.CTkButton(
            buttons_container, 
            text="📱 حفظ في الهاتف", 
            command=save_to_phone,
            fg_color="#2196F3",  # لون أزرق
            hover_color="#1976D2",
            width=150,
            height=45,
            font=("Arial", 12, "bold"),
            corner_radius=10
        )
        phone_btn.pack(side=tk.LEFT, padx=5)
        
        # زر إغلاق
        close_btn = ctk.CTkButton(
            buttons_container, 
            text="❌ إغلاق", 
            command=dialog.destroy,
            fg_color="#dc3545",  # لون أحمر
            hover_color="#c82333",
            width=120,
            height=45,
            font=("Arial", 13, "bold"),
            corner_radius=10
        )
        close_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # ربط Enter مباشر للحفظ السريع
        def on_barcode_enter(event):
            print("تم الضغط على Enter في حقل الباركود")
            try:
                customer_entry.focus_set()
                customer_entry.update()
            except Exception as e:
                print(f"خطأ في التركيز على حقل اسم العميل: {e}")
            return "break"
        
        def on_customer_enter_quick(event):
            try:
                phone_entry.focus_set()
                phone_entry.update()
            except Exception as e:
                print(f"خطأ في التركيز على حقل رقم الهاتف: {e}")
            return "break"
        
        def on_phone_enter_quick(event):
            print("تم الضغط على Enter في حقل رقم الهاتف (الحفظ السريع)")
            try:
                device_type_entry.focus_set()
                device_type_entry.update()
                print("تم التركيز على حقل نوع الجهاز (الحفظ السريع)")
            except Exception as e:
                print(f"خطأ في التركيز على حقل نوع الجهاز: {e}")
            return "break"
        
        def on_device_enter_quick(event):
            print("تم الضغط على Enter في حقل نوع الجهاز (الحفظ السريع)")
            try:
                issue_text.focus_set()
                issue_text.update()
                print("تم التركيز على حقل وصف العطل (الحفظ السريع)")
            except Exception as e:
                print(f"خطأ في التركيز على حقل وصف العطل: {e}")
            return "break"
        
        def on_issue_enter_quick(event):
            print("تم الضغط على Enter في حقل وصف العطل (الحفظ السريع)")
            try:
                save()
                print("تم حفظ الطلب (الحفظ السريع)")
            except Exception as e:
                print(f"خطأ في حفظ الطلب: {e}")
            return "break"
        
        # ربط Enter مباشر
        barcode_entry.bind('<Return>', on_barcode_enter)
        customer_entry.bind('<Return>', on_customer_enter_quick)
        phone_entry.bind('<Return>', on_phone_enter_quick)
        device_type_entry.bind('<Return>', on_device_enter_quick)
        issue_text.bind('<Return>', on_issue_enter_quick)
        
        print("✅ تم ربط Enter مباشر للحفظ السريع")
    def add_maintenance(self):
        """إضافة طلب صيانة جديد - محسن واحترافي"""
        # إنشاء نافذة الإضافة
        dialog = ctk.CTkToplevel(self)
        dialog.title("إضافة طلب صيانة جديد - ADR ELECTRONICS")
        dialog.geometry("550x750")  # نافذة محسنة
        dialog.grab_set()  # جعل النافذة مركزة
        dialog.resizable(False, False)  # منع تغيير الحجم
        
        
        # مركز النافذة على الشاشة
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (550 // 2)
        y = (dialog.winfo_screenheight() // 2) - (750 // 2)
        dialog.geometry(f"550x750+{x}+{y}")
        
        # إضافة أيقونة النافذة
        try:
            dialog.iconbitmap("icon.ico")
        except:
            pass
        
        # إجبار التركيز على النافذة
        dialog.focus_force()
        
        # متغير نوع الكود
        code_type_var = tk.StringVar(value="A")
        
        # توليد كود جديد فوراً عند فتح النافذة من قاعدة البيانات
        if hasattr(self, 'maintenance_service'):
            current_code = self.maintenance_service.generate_tracking_code(code_type_var.get())
        else:
            current_code = "A1"
        
        # محتوى النافذة الرئيسي
        main_container = ctk.CTkFrame(dialog, fg_color="transparent")
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)
        
        # عنوان النافذة المحسن
        title_frame = ctk.CTkFrame(main_container, fg_color="#1976d2", corner_radius=15)
        title_frame.pack(fill=tk.X, pady=(0, 25))
        
        # عنوان رئيسي مع أيقونة
        title_content = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_content.pack(fill=tk.X, padx=25, pady=10)
        
        ctk.CTkLabel(
            title_content, 
            text="🔧 إضافة طلب صيانة جديد", 
            font=("Arial", 22, "bold"), 
            text_color="white"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            title_content, 
            text="ADR ELECTRONICS", 
            font=("Arial", 12, "bold"), 
            text_color="#E3F2FD"
        ).pack(side=tk.RIGHT)
        
        # قسم الكود الجديد المحسن
        code_section = ctk.CTkFrame(main_container, fg_color="#e8f5e8", corner_radius=12, border_width=3, border_color="#4caf50")
        code_section.pack(fill=tk.X, pady=(0, 25))
        
        # عنوان القسم
        code_title_frame = ctk.CTkFrame(code_section, fg_color="transparent")
        code_title_frame.pack(fill=tk.X, padx=20, pady=(1, 1))
        
        ctk.CTkLabel(
            code_title_frame, 
            text="🏷️ الكود المرجعي للجهاز الجديد", 
            font=("Arial", 16, "bold"), 
            text_color="#2e7d32"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            code_title_frame, 
            text="يجب تسجيل هذا الكود على الجهاز", 
            font=("Arial", 12), 
            text_color="#4caf50"
        ).pack(side=tk.RIGHT)
        
        # قائمة اختيار نوع الكود
        code_type_frame = ctk.CTkFrame(code_section, fg_color="transparent")
        code_type_frame.pack(fill=tk.X, padx=20, pady=(0, 1))
        
        ctk.CTkLabel(
            code_type_frame,
            text="نوع الكود:",
            font=("Arial", 12, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # دالة تحديث الكود عند تغيير النوع
        def update_code_on_type_change(*args):
            """تحديث الكود عند تغيير نوع الكود"""
            try:
                selected_type = code_type_var.get()
                # استخراج الحرف من النص (مثل "A - انفرترات" -> "A")
                code_letter = selected_type.split(" - ")[0] if " - " in selected_type else selected_type
                
                # توليد كود جديد من نفس النوع
                if hasattr(self, 'maintenance_service'):
                    new_code = self.maintenance_service.generate_tracking_code(code_letter)
                else:
                    new_code = f"{code_letter}1"
                
                # تحديث عرض الكود
                code_display.configure(text=new_code)
                
            except Exception as e:
                print(f"خطأ في تحديث الكود: {e}")
        
        code_type_combo = ctk.CTkComboBox(
            code_type_frame,
            values=["A - انفرترات", "B - عده صناعيه", "C - مشكل", "D - شاشات"],
            variable=code_type_var,
            width=200,
            height=35,
            font=("Arial", 12),
            command=update_code_on_type_change
        )
        code_type_combo.pack(side=tk.LEFT)
        
        # ربط حدث التغيير أيضاً
        code_type_var.trace("w", update_code_on_type_change)
        
        # عرض الكود
        code_display_frame = ctk.CTkFrame(code_section, fg_color="transparent")
        code_display_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        code_display = ctk.CTkLabel(
            code_display_frame,
            text=current_code,
            font=("Arial", 28, "bold"),
            text_color="#1b5e20",
            fg_color="#c8e6c9",
            corner_radius=12,
            width=300,
            height=60
        )
        code_display.pack()
        
        # إطار النموذج الرئيسي مع إمكانية التمرير
        form_container = ctk.CTkScrollableFrame(main_container, fg_color="#fafafa", corner_radius=10)
        form_container.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # حقل الرقم التسلسلي المحسن
        serial_section = ctk.CTkFrame(form_container, fg_color="#ffffff", corner_radius=10, border_width=1, border_color="#e0e0e0")
        serial_section.pack(fill=tk.X, pady=(20, 15), padx=20)
        
        # عنوان الحقل مع أيقونة
        serial_title = ctk.CTkFrame(serial_section, fg_color="transparent")
        serial_title.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            serial_title, 
            text="📱 الرقم التسلسلي", 
            font=("Arial", 14, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            serial_title, 
            text="(اختياري)", 
            font=("Arial", 10),
            text_color="#666666"
        ).pack(side=tk.RIGHT)
        
        serial_entry = ctk.CTkEntry(
            serial_section, 
            width=400, 
            height=40,
            placeholder_text="ادخل الرقم التسلسلي للجهاز",
            font=("Arial", 13),
            corner_radius=8,
            border_width=2
        )
        serial_entry.pack(fill=tk.X, padx=15, pady=(0, 1))
        
        
        # تم إزالة التأثيرات البصرية المعقدة لتحسين الأداء
        
        # حقل اسم العميل المحسن
        customer_section = ctk.CTkFrame(form_container, fg_color="#ffffff", corner_radius=10, border_width=1, border_color="#e0e0e0")
        customer_section.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        # عنوان الحقل مع أيقونة
        customer_title = ctk.CTkFrame(customer_section, fg_color="transparent")
        customer_title.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            customer_title,
            text="👤 اسم العميل",
            font=("Arial", 14, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            customer_title,
            text="(مطلوب)",
            font=("Arial", 10),
            text_color="#d32f2f"
        ).pack(side=tk.RIGHT)
        
        customer_entry = ctk.CTkEntry(
            customer_section, 
            width=400, 
            height=40,
            placeholder_text="ادخل اسم العميل الكامل",
            font=("Arial", 13),
            corner_radius=8,
            border_width=2
        )
        customer_entry.pack(fill=tk.X, padx=15, pady=(0, 1))
        
        # دالة البحث عن العميل
        def search_customer_by_name(event=None):
            customer_name = customer_entry.get().strip()
            if customer_name and hasattr(self, 'maintenance_service'):
                try:
                    # البحث عن العميل في قاعدة البيانات
                    db = next(get_db())
                    from database.models import Customer
                    customer = db.query(Customer).filter(Customer.name.ilike(f"%{customer_name}%")).first()
                    db.close()
                    
                    if customer:
                        # ملء رقم الهاتف تلقائياً
                        phone_entry.delete(0, tk.END)
                        phone_entry.insert("0", customer.phone)
                        
                        # تغيير لون حقل الهاتف للإشارة إلى أنه تم ملؤه تلقائياً
                        phone_entry.configure(fg_color="#e8f5e8", border_color="#4caf50")
                        
                        # الانتقال إلى حقل نوع الجهاز
                        device_type_entry.focus()
                    else:
                        # إعادة تعيين لون حقل الهاتف
                        phone_entry.configure(fg_color=("gray95", "gray10"), border_color=("gray60", "gray30"))
                        phone_entry.configure(placeholder_text="أدخل رقم الهاتف")
                except Exception as e:
                    print(f"خطأ في البحث عن العميل: {e}")
                    phone_entry.configure(fg_color=("gray95", "gray10"), border_color=("gray60", "gray30"))
        
        # تم إزالة دالة التمرير التلقائي المعقدة لتحسين الأداء
        # ربط البحث بالانتقال من حقل اسم العميل
        customer_entry.bind('<FocusOut>', search_customer_by_name)
        
        # حقل رقم الهاتف المحسن
        phone_section = ctk.CTkFrame(form_container, fg_color="#ffffff", corner_radius=10, border_width=1, border_color="#e0e0e0")
        phone_section.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        # عنوان الحقل مع أيقونة
        phone_title = ctk.CTkFrame(phone_section, fg_color="transparent")
        phone_title.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            phone_title,
            text="📞 رقم الهاتف",
            font=("Arial", 14, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            phone_title,
            text="(مطلوب)",
            font=("Arial", 10),
            text_color="#d32f2f"
        ).pack(side=tk.RIGHT)
        
        phone_entry = ctk.CTkEntry(
            phone_section, 
            width=400, 
            height=40,
            placeholder_text="أدخل رقم الهاتف",
            font=("Arial", 13),
            corner_radius=8,
            border_width=2
        )
        phone_entry.pack(fill=tk.X, padx=15, pady=(0, 1))
        
        # تم تبسيط التنقل لتحسين الأداء
        
        # حقل نوع الجهاز المحسن
        device_section = ctk.CTkFrame(form_container, fg_color="#ffffff", corner_radius=10, border_width=1, border_color="#e0e0e0")
        device_section.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        # عنوان الحقل مع أيقونة
        device_title = ctk.CTkFrame(device_section, fg_color="transparent")
        device_title.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            device_title,
            text="💻 نوع الجهاز",
            font=("Arial", 14, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            device_title,
            text="(مطلوب)",
            font=("Arial", 10),
            text_color="#d32f2f"
        ).pack(side=tk.RIGHT)
        
        device_type_entry = ctk.CTkEntry(
            device_section, 
            width=400, 
            height=40,
            placeholder_text="مثال: هاتف، لابتوب، تابلت",
            font=("Arial", 13),
            corner_radius=8,
            border_width=2
        )
        device_type_entry.pack(fill=tk.X, padx=15, pady=(0, 1))
        
        # تم تبسيط التنقل لتحسين الأداء
        
        # حقل تفاصيل الجهاز المحسن
        device_details_section = ctk.CTkFrame(form_container, fg_color="#ffffff", corner_radius=10, border_width=1, border_color="#e0e0e0")
        device_details_section.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        # عنوان الحقل مع أيقونة
        device_details_title = ctk.CTkFrame(device_details_section, fg_color="transparent")
        device_details_title.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            device_details_title,
            text="📋 تفاصيل الجهاز",
            font=("Arial", 14, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            device_details_title,
            text="(اختياري)",
            font=("Arial", 10),
            text_color="#666666"
        ).pack(side=tk.RIGHT)
        
        device_details_entry = ctk.CTkTextbox(
            device_details_section, 
            width=400, 
            height=80,
            font=("Arial", 12),
            corner_radius=8,
            border_width=2
        )
        device_details_entry.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # تم تبسيط التنقل لتحسين الأداء
        # حقل نوع العطل المحسن
        issue_section = ctk.CTkFrame(form_container, fg_color="#ffffff", corner_radius=10, border_width=1, border_color="#e0e0e0")
        issue_section.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        # عنوان الحقل مع أيقونة
        issue_title = ctk.CTkFrame(issue_section, fg_color="transparent")
        issue_title.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            issue_title,
            text="🔧 وصف العطل",
            font=("Arial", 14, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            issue_title,
            text="(اختياري)",
            font=("Arial", 10),
            text_color="#666666"
        ).pack(side=tk.RIGHT)
        
        issue_entry = ctk.CTkEntry(
            issue_section, 
            width=400, 
            height=25,
            placeholder_text="وصف العطل أو المشكلة في الجهاز",
            font=("Arial", 12),
            corner_radius=6,
            border_width=1
        )
        issue_entry.pack(fill=tk.X, padx=15, pady=(0, 1))
        
        # تم تبسيط التنقل لتحسين الأداء
        # حقل السعر التقديري المحسن
        price_section = ctk.CTkFrame(form_container, fg_color="#ffffff", corner_radius=10, border_width=1, border_color="#e0e0e0")
        price_section.pack(fill=tk.X, pady=(0, 1), padx=20)
        
        # عنوان الحقل مع أيقونة
        price_title = ctk.CTkFrame(price_section, fg_color="transparent")
        price_title.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            price_title,
            text="💰 السعر التقديري",
            font=("Arial", 14, "bold"),
            text_color="#424242"
        ).pack(side=tk.LEFT)
        
        ctk.CTkLabel(
            price_title,
            text="(اختياري)",
            font=("Arial", 10),
            text_color="#666666"
        ).pack(side=tk.RIGHT)
        
        # إطار العملة والسعر
        price_content_frame = ctk.CTkFrame(price_section, fg_color="transparent")
        price_content_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # اختيار العملة
        estimated_currency_var = tk.StringVar(value="USD")
        currency_selection_frame = ctk.CTkFrame(price_content_frame, fg_color="transparent")
        currency_selection_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        ctk.CTkLabel(currency_selection_frame, text="العملة:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        usd_radio = ctk.CTkRadioButton(currency_selection_frame, text="💵 دولار ($)", variable=estimated_currency_var, value="USD", font=("Arial", 10))
        usd_radio.pack(anchor=tk.W)
        
        lbp_radio = ctk.CTkRadioButton(currency_selection_frame, text="💱 ليرة لبنانية (ل.ل)", variable=estimated_currency_var, value="LBP", font=("Arial", 10))
        lbp_radio.pack(anchor=tk.W)
        
        # حقل السعر
        price_input_frame = ctk.CTkFrame(price_content_frame, fg_color="transparent")
        price_input_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ctk.CTkLabel(price_input_frame, text="المبلغ:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        estimated_cost_entry = ctk.CTkEntry(
            price_input_frame, 
            width=200, 
            height=35,
            placeholder_text="أدخل السعر التقديري",
            font=("Arial", 12),
            corner_radius=8,
            border_width=2
        )
        estimated_cost_entry.pack(fill=tk.X, pady=(0, 5))
        
        # عرض التحويل
        conversion_display = ctk.CTkLabel(price_input_frame, text="", font=("Arial", 10), text_color="#666666")
        conversion_display.pack(anchor=tk.W)
        
        def update_price_conversion():
            """تحديث عرض التحويل للسعر التقديري"""
            try:
                amount = float(estimated_cost_entry.get()) if estimated_cost_entry.get() else 0
                currency = estimated_currency_var.get()
                
                if amount > 0:
                    if currency == "USD":
                        lbp_amount = amount * 90000  # سعر الصرف
                        conversion_display.configure(text=f"المبلغ بالليرة: {lbp_amount:,.0f} ل.ل")
                    else:
                        usd_amount = amount / 90000  # سعر الصرف
                        conversion_display.configure(text=f"المبلغ بالدولار: ${usd_amount:.2f}")
                else:
                    conversion_display.configure(text="")
            except ValueError:
                conversion_display.configure(text="")
        
        # ربط التحديثات
        estimated_cost_entry.bind('<KeyRelease>', lambda e: update_price_conversion())
        estimated_currency_var.trace('w', lambda *args: update_price_conversion())
        
        # تم تبسيط التنقل لتحسين الأداء
        
        # أزرار التحكم
        buttons_container = ctk.CTkFrame(main_container, fg_color="transparent")
        buttons_container.pack(fill=tk.X, pady=(20, 0))
        
        def save():
            serial = serial_entry.get().strip()
            customer_name = customer_entry.get().strip()
            phone = phone_entry.get().strip()
            device_type = device_type_entry.get().strip()
            device_details = device_details_entry.get("1.0", tk.END).strip()
            issue = issue_entry.get().strip()
            estimated_cost = estimated_cost_entry.get().strip()
            estimated_cost_currency = estimated_currency_var.get()
            
            # استخدام الكود المعروض إذا لم يتم إدخال رقم تسلسلي
            if not serial:
                serial = code_display.cget("text")
                # تحديث حقل الرقم التسلسلي بالكود المولد
                serial_entry.delete(0, tk.END)
                serial_entry.insert(0, serial)
            
            # السماح بالحفظ حتى لو لم تكتمل جميع المعلومات
            # استخدام قيم افتراضية للحقول الفارغة
            empty_fields = []
            if not customer_name:
                customer_name = "عميل غير محدد"
                empty_fields.append("اسم العميل")
            if not phone:
                phone = "غير محدد"
                empty_fields.append("رقم الهاتف")
            if not device_type:
                device_type = "غير محدد"
                empty_fields.append("نوع الجهاز")
            if not issue:
                issue = "لم يتم تحديد نوع العطل"
                empty_fields.append("نوع العطل")
            
            # معالجة السعر التقديري
            estimated_cost_value = 0.0
            if estimated_cost:
                try:
                    estimated_cost_value = float(estimated_cost)
                    # تحويل السعر إلى الدولار إذا كان بالليرة اللبنانية
                    if estimated_cost_currency == "LBP":
                        estimated_cost_value = estimated_cost_value / 90000  # تحويل إلى دولار
                except ValueError:
                    estimated_cost_value = 0.0
            
            # حفظ مباشر بدون رسائل تحذير
            
            try:
                if not hasattr(self, 'maintenance_service'):
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    return
                    
                # استخراج نوع الكود من القائمة المنسدلة
                selected_type = code_type_var.get()
                code_letter = selected_type.split(" - ")[0] if " - " in selected_type else selected_type
                
                
                success, message, job = self.maintenance_service.create_maintenance_job(                                                                        
                    customer_name=customer_name,
                    phone=phone,
                    device_type=device_type,
                    device_model=None,
                    serial_number=serial,
                    issue_description=issue,
                    estimated_cost=estimated_cost_value,
                    estimated_cost_currency=estimated_cost_currency,
                    notes=device_details if device_details else None,
                    code_type=code_letter
                )
                
                if success:
                    # تحديث الجدول سريعاً بدون إعادة تحميل ثقيلة
                    self.invalidate_data_cache()
                    self._insert_new_job_fast(
                        job_data=job,
                        customer_name=customer_name,
                        phone=phone,
                        device_type=device_type,
                        serial=serial,
                        estimated_cost_value=estimated_cost_value
                    )
                    self.update_stats(force_refresh=True)
                    
                    # حفظ بيانات العميل الأخير لاستخدامها في حفظ جهة الاتصال
                    self.last_customer_name = customer_name
                    self.last_customer_phone = phone
                    
                    # تحديث الكود للطلب التالي بنفس النوع
                    if hasattr(self, 'maintenance_service'):
                        selected_type = code_type_var.get()
                        code_letter = selected_type.split(" - ")[0] if " - " in selected_type else selected_type
                        new_code = self.maintenance_service.generate_tracking_code(code_letter)
                        code_display.configure(text=new_code)
                    
                    messagebox.showinfo("نجاح", f"تم إضافة طلب الصيانة بنجاح\nرقم التتبع: {job['tracking_code']}\nالكود الجديد: {new_code if hasattr(self, 'maintenance_service') else current_code}")
                    # مسح الحقول للطلب التالي
                    serial_entry.delete(0, tk.END)
                    customer_entry.delete(0, tk.END)
                    phone_entry.delete(0, tk.END)
                    phone_entry.configure(fg_color=("gray95", "gray10"), border_color=("gray60", "gray30"))                                                     
                    device_type_entry.delete(0, tk.END)
                    device_details_entry.delete("1.0", tk.END)
                    issue_entry.delete(0, tk.END)
                    estimated_cost_entry.delete(0, tk.END)
                    estimated_currency_var.set("USD")  # إعادة تعيين العملة للدولار                                                                             
                    conversion_display.configure(text="")  # مسح عرض التحويل
                    
                    # التركيز على حقل الرقم التسلسلي
                    serial_entry.focus()
                else:
                    messagebox.showerror("خطأ", f"فشل في حفظ البيانات: {message}")
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
        
        # دالة لحفظ البيانات عند الضغط على Enter
        def trigger_save_from_button(event=None):
            """تنفيذ الحفظ عند الضغط على Enter"""
            save()
            return "break"
        
        # --- تنقل Enter بين الحقول ---
        def focus_widget(widget):
            try:
                widget.focus_set()
                if isinstance(widget, ctk.CTkTextbox):
                    widget.focus()
            except Exception:
                pass
        
        def bind_enter(widget, next_widget=None, *, allow_shift_newline=False, on_enter_callback=None):
            """ربط مفتاح Enter للانتقال بين الحقول بالتسلسل."""
            def handler(event):
                if allow_shift_newline and isinstance(widget, ctk.CTkTextbox) and (event.state & 0x0001):
                    # السماح بإضافة سطر جديد داخل مربعات النص مع Shift+Enter
                    return
                if on_enter_callback:
                    # إذا كان هناك callback مخصص (مثل الحفظ)، قم بتشغيله
                    return on_enter_callback(event)
                if next_widget:
                    focus_widget(next_widget)
                return "break"
            widget.bind('<Return>', handler)
            widget.bind('<KP_Enter>', handler)
        
        # ربط Enter للتنقل بين الحقول
        # ربط Enter على قائمة نوع الكود للانتقال إلى حقل الرقم التسلسلي
        def on_code_type_enter(event):
            serial_entry.focus_set()
            return "break"
        code_type_combo.bind('<Return>', on_code_type_enter)
        code_type_combo.bind('<KP_Enter>', on_code_type_enter)
        
        bind_enter(serial_entry, customer_entry)
        bind_enter(customer_entry, phone_entry)
        bind_enter(phone_entry, device_type_entry)
        bind_enter(device_type_entry, device_details_entry)
        bind_enter(device_details_entry, issue_entry, allow_shift_newline=True)
        bind_enter(issue_entry, estimated_cost_entry)
        # عند الضغط على Enter في آخر حقل (السعر)، يتم الحفظ مباشرة
        bind_enter(estimated_cost_entry, on_enter_callback=trigger_save_from_button)
        
        # زر الحفظ المحسن
        save_btn = ctk.CTkButton(
            buttons_container, 
            text="💾 حفظ الطلب", 
            command=save,
            fg_color="#28a745",
            hover_color="#218838",
            width=180,
            height=50,
            font=("Arial", 15, "bold"),
            corner_radius=12,
            border_width=2,
            border_color="#1e7e34"
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 10))
        # ربط Enter على زر الحفظ لحفظ البيانات
        save_btn.bind('<Return>', trigger_save_from_button)
        save_btn.bind('<KP_Enter>', trigger_save_from_button)
        
        # بدء الإدخال من حقل الرقم التسلسلي
        try:
            serial_entry.focus_set()
            serial_entry.icursor(tk.END)
        except Exception:
            pass
        
        # زر حفظ في الهاتف
        def save_to_phone_2():
            """حفظ العميل في جهات اتصال الهاتف"""
            if hasattr(self, 'last_customer_name') and hasattr(self, 'last_customer_phone'):
                self.show_contact_save_options(self.last_customer_name, self.last_customer_phone)
            else:
                # إذا لم يتم حفظ طلب بعد، استخدم البيانات من الحقول
                name = customer_entry.get().strip()
                phone_val = phone_entry.get().strip()
                if name and phone_val:
                    self.show_contact_save_options(name, phone_val)
                else:
                    messagebox.showwarning("تنبيه", "الرجاء إدخال اسم ورقم الهاتف أو حفظ الطلب أولاً")
        
        phone_btn = ctk.CTkButton(
            buttons_container, 
            text="📱 حفظ في الهاتف", 
            command=save_to_phone_2,
            fg_color="#2196F3",
            hover_color="#1976D2",
            width=180,
            height=50,
            font=("Arial", 14, "bold"),
            corner_radius=12,
            border_width=2,
            border_color="#0d47a1"
        )
        phone_btn.pack(side=tk.LEFT, padx=10)
        
        # زر إغلاق محسن
        close_btn = ctk.CTkButton(
            buttons_container, 
            text="❌ إغلاق", 
            command=dialog.destroy,
            fg_color="#dc3545",
            hover_color="#c82333",
            width=140,
            height=50,
            font=("Arial", 15, "bold"),
            corner_radius=12,
            border_width=2,
            border_color="#bd2130"
        )
        close_btn.pack(side=tk.LEFT, padx=(15, 0))
        
        # تم إزالة setup_enter_navigation لتحسين الأداء - نستخدم ربط Enter المخصص بدلاً منه
        
        # التركيز على أول حقل
        try:
            serial_entry.focus_set()
        except:
            pass
    
    def edit_maintenance(self):
        """تعديل طلب صيانة محدد"""
        if not hasattr(self, 'tree'):
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("تحذير", "الرجاء اختيار طلب صيانة للتعديل")
            return
        
        # الحصول على معرف الطلب المحدد
        item = self.tree.item(selected[0])
        job_id = item['values'][1]  # الفهرس 1 لأن 0 يحتوي على مربع التحديد
        
        # جلب بيانات الطلب
        if not hasattr(self, 'maintenance_service'):
            messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
            return
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
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)
        
        # تبويبات التعديل - تصميم ملون وجذاب
        tabview = ctk.CTkTabview(content, 
                               fg_color=("#f0f0f0", "#2b2b2b"))
        tabview.pack(fill=tk.BOTH, expand=True, pady=(0, 1))
        
        # تبويبات التعديل - حالة الطلب أولاً
        tab_status = tabview.add("حالة الطلب")
        tab_info = tabview.add("المعلومات الأساسية")
        tab_parts = tabview.add("قطع الغيار")
        tab_payments = tabview.add("المدفوعات")
        
        # تعبئة التبويبات - حالة الطلب أولاً
        # نستخدم قاموس لتخزين مراجع الحقول
        form_fields = {}
        
        # تعبئة تبويب حالة الطلب أولاً
        self.setup_status_tab(tab_status, job)
        
        # تعبئة تبويب المعلومات الأساسية
        # تعريف دالة الحفظ قبل إعداد التبويب
        def save_changes():
            try:
                # جمع البيانات من حقول النموذج
                customer_name = form_fields['customer_entry'].get().strip()
                phone = form_fields['phone_entry'].get().strip()
                email = form_fields['email_entry'].get().strip()
                address = form_fields['address_entry'].get().strip()
                device_type = form_fields['device_type_combo'].get()
                model = form_fields['model_entry'].get().strip()
                serial = form_fields['serial_entry'].get().strip()
                issue = form_fields['issue_text'].get("1.0", tk.END).strip()
                notes = form_fields['notes_text'].get("1.0", tk.END).strip()
                
                # التحقق من البيانات المطلوبة
                if not customer_name or not phone:
                    messagebox.showwarning("تحذير", "الرجاء إدخال اسم العميل ورقم الهاتف")
                    return
                
                # تحديث بيانات العميل
                if not hasattr(self, 'maintenance_service'):
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    return
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
                if not hasattr(self, 'maintenance_service'):
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    return
                success, message = self.maintenance_service.update_maintenance_job(
                    job_id=job['id'],
                    device_type=device_type,
                    device_model=model if model else None,
                    serial_number=serial if serial else None,
                    issue_description=issue,
                    notes=notes if notes else None
                )
                
                if success:
                    messagebox.showinfo("نجاح", "✅ تم حفظ التغييرات بنجاح")
                    dialog.destroy()
                    self.load_data()
                else:
                    messagebox.showerror("خطأ", f"❌ فشل في تحديث بيانات الصيانة: {message}")
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"❌ حدث خطأ غير متوقع: {str(e)}")
        
        # تعبئة تبويب المعلومات الأساسية
        self.setup_edit_info_tab(tab_info, job, form_fields, save_changes)
        
        # تعبئة تبويب قطع الغيار
        self.setup_parts_tab(tab_parts, job)
        
        # تعبئة تبويب المدفوعات
        self.setup_payments_tab(tab_payments, job)
        
        # تعيين التبويب الافتراضي إلى "حالة الطلب"
        tabview.set("حالة الطلب")
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # تم إزالة أزرار الحفظ والإغلاق حسب طلب المستخدم
    
    def setup_edit_info_tab(self, parent, job, form_fields=None, save_function=None):
        """إعداد تبويب معلومات الطلب"""
        # حقول النموذج
        ctk.CTkLabel(parent, text="رقم التتبع:").grid(row=0, column=0, sticky=tk.W, pady=(5, 0))
        ctk.CTkLabel(parent, text=job['tracking_code'], font=("Arial", 12, "bold")).grid(row=0, column=1, sticky=tk.W, pady=(5, 0))
        
        # حقل تغيير كود التتبع
        ctk.CTkLabel(parent, text="تغيير كود التتبع:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        
        # إطار لتغيير كود التتبع
        tracking_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tracking_frame.grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        
        # اختيار نوع الكود
        code_type_combo = ctk.CTkComboBox(
            tracking_frame,
            values=["A - أجهزة عامة", "B - هواتف", "C - لابتوب", "D - أجهزة أخرى"],
            width=150
        )
        # تحديد النوع الحالي
        current_code = job['tracking_code']
        if current_code.startswith('A'):
            code_type_combo.set("A - أجهزة عامة")
        elif current_code.startswith('B'):
            code_type_combo.set("B - هواتف")
        elif current_code.startswith('C'):
            code_type_combo.set("C - لابتوب")
        elif current_code.startswith('D'):
            code_type_combo.set("D - أجهزة أخرى")
        else:
            code_type_combo.set("A - أجهزة عامة")
        
        code_type_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # زر عرض الأكواد المتاحة
        def load_available_codes():
            try:
                code_type = code_type_combo.get().split(' - ')[0]
                available_codes = self.maintenance_service.get_available_tracking_codes(code_type)
                
                # إنشاء نافذة منبثقة لعرض الأكواد المتاحة
                codes_window = ctk.CTkToplevel(parent)
                codes_window.title("الأكواد المتاحة")
                codes_window.geometry("300x200")
                codes_window.transient(parent)
                codes_window.grab_set()
                
                # إعداد التنقل بالـ Enter
                self.setup_enter_navigation(codes_window)
                
                ctk.CTkLabel(codes_window, text=f"الأكواد المتاحة للنوع {code_type}:", font=("Arial", 12, "bold")).pack(pady=10)
                
                # قائمة الأكواد
                codes_listbox = tk.Listbox(codes_window, height=8)
                codes_listbox.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
                
                for code in available_codes:
                    codes_listbox.insert(tk.END, code)
                
                # زر اختيار الكود
                def select_code():
                    selection = codes_listbox.curselection()
                    if selection:
                        selected_code = codes_listbox.get(selection[0])
                        new_code_entry.delete(0, tk.END)
                        new_code_entry.insert(0, selected_code)
                        codes_window.destroy()
                
                ctk.CTkButton(codes_window, text="اختيار الكود", command=select_code).pack(pady=10)
                
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في تحميل الأكواد المتاحة: {str(e)}")
        
        btn_load_codes = ctk.CTkButton(tracking_frame, text="عرض الأكواد", command=load_available_codes, width=100)
        btn_load_codes.pack(side=tk.LEFT, padx=(0, 5))
        
        # حقل إدخال الكود الجديد
        new_code_entry = ctk.CTkEntry(tracking_frame, width=100, placeholder_text="كود جديد")
        new_code_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # زر تحديث الكود
        def update_tracking_code():
            try:
                new_code = new_code_entry.get().strip()
                if not new_code:
                    messagebox.showwarning("تحذير", "يرجى إدخال كود جديد")
                    return
                
                if new_code == current_code:
                    messagebox.showwarning("تحذير", "الكود الجديد مطابق للكود الحالي")
                    return
                
                if not messagebox.askyesno("تأكيد", f"هل تريد تغيير كود التتبع من {current_code} إلى {new_code}؟"):
                    return
                
                # تحديث كود التتبع
                success, message = self.maintenance_service.update_maintenance_job(
                    job_id=job['id'],
                    tracking_code=new_code
                )
                
                if success:
                    messagebox.showinfo("نجاح", f"تم تحديث كود التتبع بنجاح!\nالكود الجديد: {new_code}")
                    # تحديث عرض الكود الحالي
                    parent.grid_slaves(row=0, column=1)[0].configure(text=new_code)
                    # مسح حقل الكود الجديد
                    new_code_entry.delete(0, tk.END)
                    # إعادة تحميل البيانات
                    self.load_data()
                else:
                    messagebox.showerror("خطأ", f"فشل في تحديث كود التتبع: {message}")
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ أثناء تحديث كود التتبع: {str(e)}")
        
        btn_update_code = ctk.CTkButton(tracking_frame, text="تحديث", command=update_tracking_code, width=80, fg_color="#4CAF50", hover_color="#45a049")
        btn_update_code.pack(side=tk.LEFT)
        
        ctk.CTkLabel(parent, text="تاريخ الاستلام:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        ctk.CTkLabel(parent, text=job['received_at']).grid(row=2, column=1, sticky=tk.W, pady=(5, 0))
        
        ctk.CTkLabel(parent, text="اسم العميل:").grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        customer_entry = ctk.CTkEntry(parent, width=300)
        customer_entry.insert("0", job['customer']['name'])
        customer_entry.grid(row=3, column=1, sticky=tk.W, pady=(5, 0))
        customer_entry.bind('<Return>', lambda e: phone_entry.focus())
        customer_entry.bind('<KeyPress-Return>', lambda e: phone_entry.focus())
        
        ctk.CTkLabel(parent, text="رقم الهاتف:").grid(row=4, column=0, sticky=tk.W, pady=(5, 0))
        phone_entry = ctk.CTkEntry(parent, width=200)
        phone_entry.insert("0", job['customer']['phone'])
        phone_entry.grid(row=4, column=1, sticky=tk.W, pady=(5, 0))
        phone_entry.bind('<Return>', lambda e: email_entry.focus())
        phone_entry.bind('<KeyPress-Return>', lambda e: email_entry.focus())
        
        # حقل البريد الإلكتروني
        ctk.CTkLabel(parent, text="البريد الإلكتروني:").grid(row=5, column=0, sticky=tk.W, pady=(5, 0))
        email_entry = ctk.CTkEntry(parent, width=300)
        email_value = job['customer'].get('email', '')
        if email_value:
            email_entry.insert("0", email_value)
        email_entry.grid(row=5, column=1, sticky=tk.W, pady=(5, 0))
        email_entry.bind('<Return>', lambda e: address_entry.focus())
        email_entry.bind('<KeyPress-Return>', lambda e: address_entry.focus())
        
        ctk.CTkLabel(parent, text="العنوان:").grid(row=6, column=0, sticky=tk.W, pady=(5, 0))
        address_entry = ctk.CTkEntry(parent, width=400)
        address_value = job['customer'].get('address', '')
        if address_value:
            address_entry.insert("0", address_value)
        address_entry.grid(row=6, column=1, sticky=tk.W, pady=(5, 0))
        address_entry.bind('<Return>', lambda e: device_type_combo.focus())
        address_entry.bind('<KeyPress-Return>', lambda e: device_type_combo.focus())
        
        # معلومات الجهاز
        ctk.CTkLabel(parent, text="معلومات الجهاز", font=("Arial", 12, "bold")).grid(row=7, column=0, columnspan=2, pady=(20, 10), sticky=tk.W)
        
        ctk.CTkLabel(parent, text="نوع الجهاز:").grid(row=8, column=0, sticky=tk.W, pady=(5, 0))
        device_type_combo = ctk.CTkComboBox(
            parent,
            values=["هاتف محمول", "حاسوب محمول", "حاسوب مكتبي", "تابلت", "أخرى"],
            width=200
        )
        device_type_value = job.get('device', {}).get('type', '') or job.get('device_type', '')
        device_type_combo.set(device_type_value)
        device_type_combo.grid(row=8, column=1, sticky=tk.W, pady=(5, 0))
        
        # حقل موديل الجهاز
        ctk.CTkLabel(parent, text="موديل الجهاز:").grid(row=9, column=0, sticky=tk.W, pady=(5, 0))
        model_entry = ctk.CTkEntry(parent, width=200)
        model_value = job.get('device', {}).get('model', '') or job.get('device_model', '')
        if model_value:
            model_entry.insert("0", model_value)
        model_entry.grid(row=9, column=1, sticky=tk.W, pady=(5, 0))
        model_entry.bind('<Return>', lambda e: serial_entry.focus())
        model_entry.bind('<KeyPress-Return>', lambda e: serial_entry.focus())
        
        ctk.CTkLabel(parent, text="الرقم التسلسلي:").grid(row=10, column=0, sticky=tk.W, pady=(5, 0))
        serial_entry = ctk.CTkEntry(parent, width=200)
        serial_value = job.get('device', {}).get('serial_number', '') or job.get('serial_number', '')
        if serial_value:
            serial_entry.insert("0", serial_value)
        serial_entry.grid(row=10, column=1, sticky=tk.W, pady=(5, 0))
        serial_entry.bind('<Return>', lambda e: issue_text.focus())
        serial_entry.bind('<KeyPress-Return>', lambda e: issue_text.focus())
        
        ctk.CTkLabel(parent, text="وصف العطل:").grid(row=11, column=0, sticky=tk.NW, pady=(5, 0))
        issue_text = ctk.CTkTextbox(parent, width=400, height=30)
        issue_value = job.get('issue', '') or job.get('issue_description', '')
        if issue_value:
            issue_text.insert("1.0", issue_value)
        issue_text.grid(row=11, column=1, sticky=tk.W, pady=(5, 0))
        issue_text.bind('<Return>', lambda e: notes_text.focus())
        issue_text.bind('<KeyPress-Return>', lambda e: notes_text.focus())
        
        ctk.CTkLabel(parent, text="ملاحظات:").grid(row=12, column=0, sticky=tk.NW, pady=(5, 0))
        notes_text = ctk.CTkTextbox(parent, width=400, height=30)
        notes_value = job.get('notes', '')
        if notes_value:
            notes_text.insert("1.0", notes_value)
        notes_text.grid(row=12, column=1, sticky=tk.W, pady=(5, 0))
        
        # تخزين مراجع الحقول في القاموس إذا تم تمريره
        if form_fields is not None:
            form_fields['customer_entry'] = customer_entry
            form_fields['phone_entry'] = phone_entry
            form_fields['email_entry'] = email_entry
            form_fields['address_entry'] = address_entry
            form_fields['device_type_combo'] = device_type_combo
            form_fields['model_entry'] = model_entry
            form_fields['serial_entry'] = serial_entry
            form_fields['issue_text'] = issue_text
            form_fields['notes_text'] = notes_text
        
        # زر حفظ التغييرات داخل التبويب
        if save_function is not None:
            save_btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
            save_btn_frame.grid(row=13, column=0, columnspan=2, pady=(20, 0))
            
            ctk.CTkButton(
                save_btn_frame,
                text="حفظ معلومات الجهاز",
                command=save_function,
                fg_color="#4CAF50",
                hover_color="#45a049",
                width=200,
                height=40
            ).pack(pady=10)
        
        # تكوين الأعمدة
        parent.columnconfigure(1, weight=1)
    
    def setup_status_tab(self, parent, job):
        """إعداد تبويب حالة الطلب"""
        # معلومات الحالة الحالية - تصميم مضغوط مع ألوان جذابة
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.pack(fill=tk.X, padx=2, pady=1)
        
        ctk.CTkLabel(status_frame, text="الحالة الحالية:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 1))
        
        # إطار الأزرار المضغوط
        buttons_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=1)
        
        status_var = tk.StringVar(value=job['status'])
        statuses = [
            ("received", "تم الاستلام", "#4CAF50"),  # أخضر
            ("not_repaired", "لم تتم الصيانة", "#9E9E9E"),  # رمادي
            ("repaired", "تم الصيانة", "#FF9800"),   # برتقالي
            ("delivered", "تم التسليم", "#2196F3")   # أزرق
        ]
        
        for i, (status, label, color) in enumerate(statuses):
            btn = ctk.CTkButton(
                buttons_frame,
                text=label,
                width=120,
                height=35,
                fg_color=color if status_var.get() == status else "#E0E0E0",
                hover_color=color,
                text_color="white" if status_var.get() == status else "black",
                font=("Arial", 10, "bold"),
                command=lambda s=status: update_status_button(s)
            )
            btn.pack(side=tk.LEFT, padx=2, pady=1)
        
        # دالة تحديث أزرار الحالة
        def update_status_buttons():
            for widget in buttons_frame.winfo_children():
                if isinstance(widget, ctk.CTkButton):
                    status = widget.cget("text")
                    if status == "تم الاستلام":
                        widget.configure(fg_color="#4CAF50" if status_var.get() == "received" else "#E0E0E0")
                    elif status == "تم الصيانة":
                        widget.configure(fg_color="#FF9800" if status_var.get() == "repaired" else "#E0E0E0")
                    elif status == "تم التسليم":
                        widget.configure(fg_color="#2196F3" if status_var.get() == "delivered" else "#E0E0E0")
        
        # ربط دالة التحديث
        status_var.trace('w', lambda *args: update_status_buttons())
        
        # دالة تحديث أزرار الحالة
        def update_status_button(status):
            status_var.set(status)
            update_status_buttons()
        
        # حقل الملاحظات
        # حقول إضافية للسعر ونوع العطل (تظهر عند اختيار "تمت صيانته")
        price_frame = ctk.CTkFrame(parent, fg_color="transparent")
        price_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        # عنوان السعر
        ctk.CTkLabel(price_frame, text="سعر الصيانة:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        # إطار العملة والسعر
        currency_price_frame = ctk.CTkFrame(price_frame, fg_color="transparent")
        currency_price_frame.pack(fill=tk.X, pady=(0, 5))
        
        # اختيار العملة
        currency_var = tk.StringVar(value="USD")
        currency_frame = ctk.CTkFrame(currency_price_frame, fg_color="transparent")
        currency_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        ctk.CTkLabel(currency_frame, text="العملة:", font=("Arial", 10)).pack(anchor=tk.W)
        usd_radio = ctk.CTkRadioButton(currency_frame, text="💵 دولار ($)", variable=currency_var, value="USD", font=("Arial", 9))
        usd_radio.pack(anchor=tk.W)
        
        lbp_radio = ctk.CTkRadioButton(currency_frame, text="💱 ليرة لبنانية (ل.ل)", variable=currency_var, value="LBP", font=("Arial", 9))
        lbp_radio.pack(anchor=tk.W)
        
        # حقل السعر
        price_entry_frame = ctk.CTkFrame(currency_price_frame, fg_color="transparent")
        price_entry_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ctk.CTkLabel(price_entry_frame, text="المبلغ:", font=("Arial", 10)).pack(anchor=tk.W)
        price_entry = ctk.CTkEntry(price_entry_frame, width=200, placeholder_text="أدخل السعر")
        price_entry.pack(fill=tk.X, pady=(0, 5))
        
        # عرض التحويل
        conversion_label = ctk.CTkLabel(price_entry_frame, text="", font=("Arial", 9), text_color="#666666")
        conversion_label.pack(anchor=tk.W)
        
        def update_conversion():
            """تحديث عرض التحويل"""
            try:
                amount = float(price_entry.get()) if price_entry.get() else 0
                currency = currency_var.get()
                
                if amount > 0:
                    if currency == "USD":
                        lbp_amount = amount * 90000  # سعر الصرف
                        conversion_label.configure(text=f"المبلغ بالليرة: {lbp_amount:,.0f} ل.ل")
                    else:
                        usd_amount = amount / 90000  # سعر الصرف
                        conversion_label.configure(text=f"المبلغ بالدولار: ${usd_amount:.2f}")
                else:
                    conversion_label.configure(text="")
            except ValueError:
                conversion_label.configure(text="")
        
        # ربط التحديثات
        price_entry.bind('<KeyRelease>', lambda e: update_conversion())
        currency_var.trace('w', lambda *args: update_conversion())
        
        ctk.CTkLabel(price_frame, text="نوع العطل:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(10, 1))
        issue_type_entry = ctk.CTkEntry(price_frame, width=300, placeholder_text="مثال: كسر الشاشة، مشكلة في البطارية")
        issue_type_entry.pack(fill=tk.X, pady=(0, 1))
        
        # إخفاء حقول السعر في البداية
        price_frame.pack_forget()
        
        # دالة لإظهار/إخفاء حقول السعر
        def toggle_price_fields():
            if status_var.get() == "repaired" or status_var.get() == "delivered":
                price_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
            else:
                price_frame.pack_forget()
        
        # ربط دالة التبديل بتغيير الحالة
        status_var.trace('w', lambda *args: toggle_price_fields())
        
        
        # إطار حالة الدفع (يظهر فقط عند التسليم)
        payment_frame = ctk.CTkFrame(parent, fg_color="#f0f0f0", corner_radius=10)
        payment_frame.pack(fill=tk.X, padx=5, pady=(5, 5))
        
        ctk.CTkLabel(
            payment_frame, 
            text="💰 حالة الدفع (عند التسليم):", 
            font=("Arial", 12, "bold")
        ).pack(anchor=tk.W, padx=10, pady=(5, 3))
        
        # القيمة الافتراضية: كاش (مفضل دائماً)
        current_payment = job.get('payment_status', 'paid_cash')  # الكاش هو الافتراضي دائماً
        if current_payment == 'unpaid':
            current_payment = 'paid_cash'  # تحويل الدين إلى كاش كافتراضي
        
        payment_status_var = tk.StringVar(value=current_payment)
        
        # أزرار اختيار حالة الدفع - تصميم مضغوط مع ألوان جذابة
        payment_options_frame = ctk.CTkFrame(payment_frame, fg_color="transparent")
        payment_options_frame.pack(fill=tk.X, padx=10, pady=1)
        
        # أزرار الدفع بجانب بعض
        payment_buttons_frame = ctk.CTkFrame(payment_options_frame, fg_color="transparent")
        payment_buttons_frame.pack(fill=tk.X, pady=1)
        
        # أزرار الدفع مع ألوان جذابة - الكاش أولاً
        payment_options = [
            ("paid_cash", "💵 كاش", "#4CAF50"),      # أخضر - الأول والأفضل
            ("paid_wish", "💳 Wish", "#FF9800"),     # برتقالي
            ("unpaid", "📝 دين", "#F44336")          # أحمر
        ]
        
        for i, (value, text, color) in enumerate(payment_options):
            btn = ctk.CTkButton(
                payment_buttons_frame,
                text=text,
                width=100,
                height=35,
                fg_color=color if payment_status_var.get() == value else "#E0E0E0",
                hover_color=color,
                text_color="white" if payment_status_var.get() == value else "black",
                font=("Arial", 10, "bold"),
                command=lambda v=value: update_payment_button(v)
            )
            btn.pack(side=tk.LEFT, padx=2, pady=1)
        
        # دالة تحديث أزرار الدفع
        def update_payment_buttons():
            for widget in payment_buttons_frame.winfo_children():
                if isinstance(widget, ctk.CTkButton):
                    text = widget.cget("text")
                    if text == "💵 كاش":
                        widget.configure(fg_color="#4CAF50" if payment_status_var.get() == "paid_cash" else "#E0E0E0")
                    elif text == "💳 Wish":
                        widget.configure(fg_color="#FF9800" if payment_status_var.get() == "paid_wish" else "#E0E0E0")
                    elif text == "📝 دين":
                        widget.configure(fg_color="#F44336" if payment_status_var.get() == "unpaid" else "#E0E0E0")
        
        # ربط دالة التحديث
        payment_status_var.trace('w', lambda *args: update_payment_buttons())
        
        # دالة تحديث أزرار الدفع
        def update_payment_button(value):
            payment_status_var.set(value)
            update_payment_buttons()
        
        ctk.CTkLabel(
            payment_frame,
            text="⚠️ سيتم حفظ حالة الدفع عند تغيير الحالة إلى 'تم التسليم'",
            font=("Arial", 9),
            text_color="#666666"
        ).pack(anchor=tk.W, padx=10, pady=(5, 10))
        
        # زر تحديث الحالة
        def update_status():
            new_status = status_var.get()
            price = price_entry.get().strip()
            issue_type = issue_type_entry.get().strip()
            payment_choice = payment_status_var.get()
            
            # استخدام ملاحظة افتراضية
            notes = f"تم تحديث الحالة إلى {new_status}"
            
            # متغير لتخزين السعر النهائي
            final_price = None
            
            # إذا كانت الحالة "جاهز للتسليم" أو "تم التسليم"، أضف السعر ونوع العطل إذا كانا متوفرين
            if new_status == "repaired" or new_status == "delivered":
                if price:
                    currency = currency_var.get()
                    # تحويل السعر إلى الدولار إذا كان بالليرة اللبنانية
                    if currency == "LBP":
                        try:
                            price_usd = float(price) / 90000  # تحويل إلى دولار
                            notes += f"\nالسعر: {price} ل.ل (${price_usd:.2f})"
                            final_price = price_usd
                        except ValueError:
                            notes += f"\nالسعر: {price} ل.ل"
                            try:
                                final_price = float(price) / 90000
                            except:
                                final_price = None
                    else:
                        notes += f"\nالسعر: {price} $"
                        try:
                            final_price = float(price)
                        except ValueError:
                            final_price = None
                    
                    # تحديث السعر النهائي
                    if final_price is not None:
                        try:
                            if hasattr(self, 'maintenance_service'):
                                self.maintenance_service.update_maintenance_job(
                                    job_id=job['id'],
                                    final_cost=final_price,
                                    final_cost_currency=currency
                                )
                        except Exception as e:
                            print(f"خطأ في تحديث السعر: {e}")
                        
                if issue_type:
                    notes += f"\nنوع العطل: {issue_type}"
            
            try:
                if not hasattr(self, 'maintenance_service'):
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    return
                    
                success, message = self.maintenance_service.update_job_status(
                    job_id=job['id'],
                    new_status=new_status,
                    notes=notes,
                    user_id=1
                )
                
                if success:
                    # إذا كانت الحالة "تم التسليم"، حفظ حالة الدفع
                    if new_status == "delivered":
                        # القيمة الافتراضية: كاش (مفضل دائماً)
                        payment_status = "paid"
                        payment_method = "cash"
                        
                        if payment_choice == "paid_wish":
                            payment_status = "paid"
                            payment_method = "wish_money"
                        elif payment_choice == "unpaid":
                            payment_status = "unpaid"
                            payment_method = None
                        else:
                            # إذا لم يتم اختيار شيء، الكاش هو الافتراضي
                            payment_status = "paid"
                            payment_method = "cash"
                        
                        # تحديث حالة الدفع
                        self.maintenance_service.update_payment_status(
                            job_id=job['id'],
                            payment_status=payment_status,
                            payment_method=payment_method
                        )
                        
                        # إذا كان التسليم كدين (unpaid)، إضافة الدين تلقائياً للحساب المميز
                        if payment_status == "unpaid":
                            print(f"🔍 حالة الدفع: دين (unpaid) - جارٍ إضافة الدين تلقائياً...")
                            # استخدام السعر النهائي المحدد في نفس الدالة
                            debt_amount = 0
                            
                            # أولاً: استخدام السعر من المتغير final_price إذا كان محدداً
                            if final_price is not None and final_price > 0:
                                debt_amount = final_price
                                print(f"✅ تم الحصول على السعر من final_price: {debt_amount:.2f} $")
                            else:
                                print(f"⚠️ final_price غير محدد، جارٍ البحث في قاعدة البيانات...")
                                # إذا لم يكن السعر محدداً، محاولة الحصول عليه من قاعدة البيانات
                                try:
                                    db = next(get_db())
                                    job_obj = db.query(MaintenanceJob).filter(MaintenanceJob.id == job['id']).first()
                                    if job_obj:
                                        debt_amount = job_obj.final_cost or job_obj.estimated_cost or 0
                                        print(f"📊 السعر من قاعدة البيانات: final_cost={job_obj.final_cost}, estimated_cost={job_obj.estimated_cost}, debt_amount={debt_amount}")
                                    else:
                                        print(f"❌ لم يتم العثور على طلب الصيانة برقم: {job['id']}")
                                    db.close()
                                except Exception as e:
                                    print(f"❌ خطأ في الحصول على السعر: {e}")
                            
                            # إذا كان السعر محدداً، إضافة الدين
                            if debt_amount > 0:
                                print(f"💰 محاولة إضافة دين بقيمة {debt_amount:.2f} $ للطلب {job['id']}")
                                self.add_debt_to_vip_account(job['id'], debt_amount)
                            else:
                                print(f"⚠️ لم يتم إضافة الدين: السعر غير محدد أو يساوي 0 (debt_amount={debt_amount})")
                        else:
                            print(f"ℹ️ حالة الدفع: {payment_status} (ليس ديناً، لن يتم إضافة معاملة)")
                    
                    # إرسال إشعار واتساب
                    price_currency = currency_var.get() if new_status == "repaired" and price else None
                    whatsapp_url = self.generate_whatsapp_notification(
                        job['id'],
                        new_status,
                        price if new_status == "repaired" else "",
                        price_currency
                    )
                    if whatsapp_url:
                        # سؤال المستخدم إذا أراد إرسال إشعار
                        if messagebox.askyesno("إشعار واتساب", "هل تريد إرسال إشعار للعميل عبر واتساب؟"):
                            webbrowser.open(whatsapp_url)
                            messagebox.showinfo("نجح", f"✅ {message}\n📱 تم فتح واتساب لإرسال الإشعار")
                        else:
                            messagebox.showinfo("نجح", f"✅ {message}")
                    else:
                        # عرض رسالة نجاح
                        messagebox.showinfo("نجح", f"✅ {message}")
                    
                    # إغلاق النافذة وتحديث البيانات
                    parent.winfo_toplevel().destroy()
                    self.load_data()
                else:
                    # إذا فشل التحديث، أظهر رسالة خطأ
                    messagebox.showerror("خطأ", f"❌ فشل تحديث الحالة:\n{message}")
                    
            except Exception as e:
                # عرض الخطأ للمستخدم
                messagebox.showerror("خطأ", f"❌ حدث خطأ غير متوقع:\n{str(e)}")
        
        ctk.CTkButton(
            parent,
            text="تحديث الحالة",
            command=update_status
        ).pack(pady=2)
    def add_debt_to_vip_account(self, job_id, amount):
        """إضافة دين تلقائياً لحساب العميل المميز عند تسليم الجهاز كدين"""
        try:
            if amount <= 0:
                print(f"⚠️ لم يتم إضافة الدين: المبلغ غير صحيح ({amount})")
                return
            
            db = next(get_db())
            
            # الحصول على طلب الصيانة
            job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
            if not job:
                print(f"❌ لم يتم العثور على طلب الصيانة برقم: {job_id}")
                db.close()
                return
            
            print(f"🔍 جارٍ التحقق من حساب العميل للطلب {job.tracking_code}...")
            
            # التحقق من أن العميل له حساب مميز
            vip_customer = db.query(VIPCustomer).filter(
                VIPCustomer.customer_id == job.customer_id
            ).first()
            
            if not vip_customer:
                print(f"⚠️ العميل '{job.customer.name if job.customer else 'غير معروف'}' ليس عميل مميز")
                db.close()
                return  # العميل ليس عميل مميز، لا حاجة لإضافة الدين
            
            print(f"✅ تم العثور على حساب مميز للعميل: {vip_customer.id}")
            
            # التحقق من عدم وجود معاملة مسبقة لهذا الطلب
            existing_transaction = db.query(AccountTransaction).filter(
                AccountTransaction.maintenance_job_id == job_id,
                AccountTransaction.transaction_type == "debt"
            ).first()
            
            if existing_transaction:
                print(f"⚠️ تم إضافة الدين مسبقاً للطلب {job.tracking_code}")
                db.close()
                return  # تم إضافة الدين مسبقاً
            
            # إضافة معاملة الدين
            transaction = AccountTransaction(
                vip_customer_id=vip_customer.id,
                maintenance_job_id=job_id,
                transaction_type="debt",
                amount=amount,
                description=f"دين من طلب الصيانة رقم {job.tracking_code} - {job.device_type}",
                created_by_id=1  # يمكن تغيير هذا لاحقاً
            )
            
            db.add(transaction)
            db.commit()
            db.close()
            
            print(f"✅ تم إضافة دين {amount:.2f} $ تلقائياً لحساب العميل المميز (VIP ID: {vip_customer.id})")
            print(f"   - رقم الطلب: {job.tracking_code}")
            print(f"   - نوع الجهاز: {job.device_type}")
            print(f"   - معرف المعاملة: {transaction.id}")
            
            # تحديث صفحة VIP إذا كانت مفتوحة
            self.refresh_vip_window_if_open(vip_customer.id)
            
        except Exception as e:
            print(f"❌ خطأ في إضافة الدين للحساب المميز: {str(e)}")
            import traceback
            print(traceback.format_exc())
            try:
                db.close()
            except:
                pass
    
    def refresh_vip_window_if_open(self, vip_id):
        """تحديث نافذة VIP إذا كانت مفتوحة"""
        try:
            if hasattr(self, 'open_vip_windows'):
                for vip_window in self.open_vip_windows[:]:  # نسخ القائمة لتجنب مشاكل التعديل
                    try:
                        # التحقق من أن النافذة لا تزال موجودة
                        if vip_window.winfo_exists():
                            # إذا كان نفس العميل محدد، حدّث البيانات
                            if hasattr(vip_window, 'current_vip_id') and vip_window.current_vip_id == vip_id:
                                vip_window.load_customer_transactions(vip_id)
                                print(f"✅ تم تحديث صفحة VIP للعميل {vip_id}")
                        else:
                            # إزالة النافذة المغلقة من القائمة
                            self.open_vip_windows.remove(vip_window)
                    except:
                        # إذا كانت النافذة مغلقة، إزالتها من القائمة
                        try:
                            self.open_vip_windows.remove(vip_window)
                        except:
                            pass
        except Exception as e:
            print(f"⚠️ خطأ في تحديث صفحة VIP: {e}")
    
    # تم دمج هذه الدوال في دالة update_status الرئيسية
    
    def show_save_contact_dialog(self):
        """عرض نافذة لإدخال بيانات العميل وحفظها في الهاتف"""
        # إنشاء نافذة الإدخال
        dialog = ctk.CTkToplevel(self)
        dialog.title("📱 حفظ عميل في الهاتف")
        dialog.geometry("500x350")
        dialog.grab_set()
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # مركز النافذة
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (350 // 2)
        dialog.geometry(f"500x350+{x}+{y}")
        
        # العنوان
        ctk.CTkLabel(
            dialog,
            text="📱 حفظ عميل في جهات اتصال الهاتف",
            font=("Arial", 18, "bold")
        ).pack(pady=10)
        
        # حقل الاسم
        name_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        name_frame.pack(pady=3, padx=40, fill="x")
        
        ctk.CTkLabel(name_frame, text="اسم العميل:", font=("Arial", 14)).pack(anchor="w", pady=2)
        name_entry = ctk.CTkEntry(name_frame, height=40, font=("Arial", 13), 
                                   placeholder_text="أدخل اسم العميل")
        name_entry.pack(fill="x", pady=2)
        name_entry.focus()
        name_entry.bind('<Return>', lambda e: phone_entry.focus())
        name_entry.bind('<KeyPress-Return>', lambda e: phone_entry.focus())
        
        # حقل الهاتف
        phone_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        phone_frame.pack(pady=3, padx=40, fill="x")
        
        ctk.CTkLabel(phone_frame, text="رقم الهاتف:", font=("Arial", 14)).pack(anchor="w", pady=2)
        phone_entry = ctk.CTkEntry(phone_frame, height=40, font=("Arial", 13),
                                    placeholder_text="أدخل رقم الهاتف")
        phone_entry.pack(fill="x", pady=2)
        
        # ربط Enter للانتقال بين الحقول
        name_entry.bind('<Return>', lambda e: phone_entry.focus())
        name_entry.bind('<KeyPress-Return>', lambda e: phone_entry.focus())
        phone_entry.bind('<Return>', lambda e: save_contact())
        phone_entry.bind('<KeyPress-Return>', lambda e: save_contact())
        
        # دالة الحفظ
        def save_contact():
            name = name_entry.get().strip()
            phone = phone_entry.get().strip()
            
            if not name or not phone:
                messagebox.showwarning("تنبيه", "الرجاء إدخال اسم العميل ورقم الهاتف")
                return
            
            dialog.destroy()
            self.show_contact_save_options(name, phone)
        
        # الأزرار
        buttons_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons_frame.pack(pady=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="💾 حفظ في الهاتف",
            command=save_contact,
            width=200,
            height=50,
            font=("Arial", 15, "bold"),
            fg_color="#4CAF50",
            hover_color="#45a049"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="❌ إلغاء",
            command=dialog.destroy,
            width=150,
            height=50,
            font=("Arial", 15, "bold"),
            fg_color="#dc3545",
            hover_color="#c82333"
        ).pack(side="left", padx=10)
    
    def ask_save_contact(self, customer_name, phone):
        """سؤال المستخدم عن حفظ جهة الاتصال في الهاتف"""
        result = messagebox.askyesno(
            "حفظ جهة الاتصال",
            f"هل تريد حفظ {customer_name} في جهات الاتصال؟"
        )
        
        if result:
            self.show_contact_save_options(customer_name, phone)
    
    def show_contact_save_options(self, customer_name, phone):
        """عرض خيارات حفظ جهة الاتصال"""
        # إنشاء نافذة الخيارات
        dialog = ctk.CTkToplevel(self)
        dialog.title("حفظ جهة الاتصال")
        dialog.geometry("400x300")
        dialog.grab_set()
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # مركز النافذة
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (300 // 2)
        dialog.geometry(f"400x300+{x}+{y}")
        
        # العنوان
        ctk.CTkLabel(
            dialog,
            text=f"📱 حفظ {customer_name}",
            font=("Arial", 18, "bold")
        ).pack(pady=10)
        
        ctk.CTkLabel(
            dialog,
            text=f"الهاتف: {phone}",
            font=("Arial", 12)
        ).pack(pady=2)
        
        # الخيارات
        def save_as_vcard():
            """حفظ كملف vCard وفتحه"""
            try:
                vcard_path = self.vcard_generator.create_vcard(
                    name=customer_name,
                    phone=phone
                )
                
                # فتح الملف في البرنامج الافتراضي
                success = self.vcard_generator.open_in_system(vcard_path)
                
                if success:
                    messagebox.showinfo(
                        "نجح",
                        f"✅ تم إنشاء ملف جهة الاتصال!\n\nالملف: {vcard_path}\n\nيمكنك:\n• فتح الملف\n• إرساله عبر واتساب\n• مشاركته عبر بلوتوث"
                    )
                else:
                    messagebox.showinfo(
                        "تم الإنشاء",
                        f"تم إنشاء الملف:\n{vcard_path}\n\nيمكنك فتحه من مجلد contacts"
                    )
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في إنشاء الملف: {str(e)}")
        
        def create_qr_code():
            """إنشاء QR Code لجهة الاتصال"""
            try:
                # إنشاء vCard أولاً
                vcard_path = self.vcard_generator.create_vcard(
                    name=customer_name,
                    phone=phone
                )
                
                # إنشاء QR Code
                qr_path = self.vcard_generator.create_qr_code(vcard_path)
                
                # فتح صورة QR
                self.vcard_generator.open_in_system(qr_path)
                
                messagebox.showinfo(
                    "نجح",
                    f"✅ تم إنشاء QR Code!\n\nيمكن مسحه بكاميرا الهاتف لحفظ جهة الاتصال\n\nالملف: {qr_path}"
                )
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في إنشاء QR Code: {str(e)}")
        
        def open_folder():
            """فتح مجلد جهات الاتصال"""
            import os
            import platform
            import subprocess
            
            contacts_dir = "contacts"
            if not os.path.exists(contacts_dir):
                os.makedirs(contacts_dir)
            
            try:
                system = platform.system()
                if system == 'Windows':
                    os.startfile(contacts_dir)
                elif system == 'Darwin':  # macOS
                    subprocess.run(['open', contacts_dir])
                else:  # Linux
                    subprocess.run(['xdg-open', contacts_dir])
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في فتح المجلد: {str(e)}")
        
        # الأزرار
        ctk.CTkButton(
            dialog,
            text="📄 حفظ كملف vCard",
            command=save_as_vcard,
            width=300,
            height=50,
            font=("Arial", 14),
            fg_color="#4CAF50",
            hover_color="#45a049"
        ).pack(pady=2)
        
        ctk.CTkButton(
            dialog,
            text="📱 إنشاء QR Code",
            command=create_qr_code,
            width=300,
            height=50,
            font=("Arial", 14),
            fg_color="#2196F3",
            hover_color="#1976D2"
        ).pack(pady=2)
        
        ctk.CTkButton(
            dialog,
            text="📁 فتح مجلد الملفات",
            command=open_folder,
            width=300,
            height=40,
            font=("Arial", 12),
            fg_color="#FF9800",
            hover_color="#F57C00"
        ).pack(pady=2)
    
        
        # سجل تغييرات الحالة
        ctk.CTkLabel(parent, text="سجل التغييرات:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=5, pady=(20, 5))
        
        # إنشاء جدول سجل التغييرات
        columns = ("date", "status", "user", "notes")
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        # تحسين الخط في القائمة
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 9))
        style.configure("Treeview.Heading", font=("Arial", 9, "bold"))
        
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
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=2)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_parts_tab(self, parent, job):
        """إعداد تبويب قطع الغيار"""
        # إطار إضافة قطعة غيار جديدة
        add_frame = ctk.CTkFrame(parent)
        add_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ctk.CTkLabel(add_frame, text="إضافة قطعة غيار:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 1))
        
        # حقول إضافة قطعة غيار
        part_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        part_frame.pack(fill=tk.X, pady=2)
        
        ctk.CTkLabel(part_frame, text="القطعة:").grid(row=0, column=0, padx=5, pady=2)
        part_combo = ctk.CTkComboBox(part_frame, width=200)
        part_combo.grid(row=0, column=1, padx=5, pady=2)
        
        ctk.CTkLabel(part_frame, text="الكمية:").grid(row=0, column=2, padx=5, pady=2)
        qty_entry = ctk.CTkEntry(part_frame, width=80)
        qty_entry.insert("0", "1")
        qty_entry.grid(row=0, column=3, padx=5, pady=2)
        
        ctk.CTkLabel(part_frame, text="السعر:").grid(row=0, column=4, padx=5, pady=2)
        price_entry = ctk.CTkEntry(part_frame, width=100)
        price_entry.grid(row=0, column=5, padx=5, pady=2)
        
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
        ctk.CTkLabel(parent, text="قطع الغيار المستخدمة:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 3))
        
        columns = ("part", "qty", "price", "total")
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        # تحسين الخط في القائمة
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 9))
        style.configure("Treeview.Heading", font=("Arial", 9, "bold"))
        
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
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=2)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def setup_payments_tab(self, parent, job):
        """إعداد تبويب المدفوعات"""
        # إطار إضافة دفعة جديدة
        add_frame = ctk.CTkFrame(parent)
        add_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ctk.CTkLabel(add_frame, text="تسجيل دفعة جديدة:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 1))
        
        # حقول إضافة دفعة
        payment_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        payment_frame.pack(fill=tk.X, pady=2)
        
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
        summary_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # حساب الإحصائيات
        total_cost = job.get('final_cost', job.get('estimated_cost', 0)) or 0
        total_paid = sum(p['amount'] for p in job.get('payments', []) if p['status'] != 'cancelled')
        remaining = max(0, total_cost - total_paid)
        
        # عرض الإحصائيات
        stats = [
            ("إجمالي التكلفة:", f"{total_cost:.2f} $"),
            ("المدفوع:", f"{total_paid:.2f} $"),
            ("المتبقي:", f"{remaining:.2f} $")
        ]
        
        for i, (label, value) in enumerate(stats):
            ctk.CTkLabel(summary_frame, text=label, font=("Arial", 12, "bold")).grid(row=0, column=i*2, padx=10, pady=2, sticky=tk.E)
            ctk.CTkLabel(summary_frame, text=value, font=("Arial", 12)).grid(row=0, column=i*2+1, padx=(0, 20), pady=2, sticky=tk.W)
        
        # جدول المدفوعات
        ctk.CTkLabel(parent, text="سجل المدفوعات:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 3))
        
        columns = ("date", "amount", "method", "status", "notes")
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        # تحسين الخط في القائمة
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 9))
        style.configure("Treeview.Heading", font=("Arial", 9, "bold"))
        
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
        tree.column("notes", width=200, anchor=tk.W)
        
        # إضافة البيانات
        for payment in job.get('payments', []):
            tree.insert("", tk.END, values=(
                payment['created_at'],
                f"{payment['amount']:.2f}",
                payment['payment_method'],
                payment['status'],
                payment.get('notes', '')
            ))
        
        # إضافة شريط التمرير
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        
        # تعبئة واجهة المستخدم
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=2)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def delete_maintenance(self):
        """حذف طلب صيانة محدد"""
        if not hasattr(self, 'tree'):
            return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("تحذير", "الرجاء اختيار طلب صيانة للحذف")
            return
        
        # تأكيد الحذف
        if not messagebox.askyesno("تأكيد الحذف", "هل أنت متأكد من حذف طلب الصيانة المحدد؟"):
            return
        
        # الحصول على معرف الطلب المحدد
        item = self.tree.item(selected[0])
        job_id = item['values'][1]  # الفهرس 1 لأن 0 يحتوي على مربع التحديد
        
        try:
            # حذف الطلب
            if not hasattr(self, 'maintenance_service'):
                messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                return
            success, message = self.maintenance_service.delete_job(job_id)
            
            if success:
                messagebox.showinfo("نجاح", message)
                self.load_data()  # تحديث الجدول
            else:
                messagebox.showerror("خطأ", message)
                
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
    
    def search_maintenance(self):
        """بحث في طلبات الصيانة - عرض النتائج في نافذة منفصلة"""
        if not hasattr(self, 'search_var'):
            return
        search_term = self.search_var.get().strip()
        
        # إذا كان حقل البحث فارغاً، قم بتحميل كافة البيانات
        if not search_term:
            self.load_data()
            return
        
        try:
            # البحث عن الطلبات المطابقة
            if not hasattr(self, 'maintenance_service'):
                messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                return
            success, message, jobs = self.maintenance_service.search_jobs(
                query=search_term
            )
            
            if success:
                if len(jobs) == 0:
                    messagebox.showinfo("لا توجد نتائج", f"لم يتم العثور على نتائج للبحث: {search_term}")
                    return
                
                # فتح نافذة البحث
                self.show_search_results_window(jobs, search_term)
                
            else:
                messagebox.showerror("خطأ", f"فشل في البحث: {message}")
                
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
    
    def show_search_results_window(self, jobs, search_term):
        """عرض نتائج البحث في نافذة منفصلة"""
        # إنشاء النافذة
        results_window = ctk.CTkToplevel(self)
        results_window.title(f"نتائج البحث: {search_term}")
        results_window.geometry("1200x600")
        results_window.grab_set()
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(results_window)
        
        # إطار العنوان
        header_frame = ctk.CTkFrame(results_window, fg_color="#2196F3", corner_radius=0)
        header_frame.pack(fill=tk.X, pady=0)
        
        ctk.CTkLabel(
            header_frame,
            text=f"🔍 نتائج البحث: {search_term} ({self.format_number_english(len(jobs))} نتيجة)",
            font=("Arial", 18, "bold"),
            text_color="white"
        ).pack(pady=15)
        
        # إنشاء Treeview للنتائج
        results_frame = ctk.CTkFrame(results_window)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # تعريف الأعمدة
        columns = ("id", "tracking_code", "customer_name", "customer_phone", "device_type", 
                   "serial_number", "status", "price", "payment", "received_date")
        
        results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=25)
        
        # تكوين العناوين
        results_tree.heading("id", text="#")
        results_tree.heading("tracking_code", text="رقم التتبع")
        results_tree.heading("customer_name", text="اسم العميل")
        results_tree.heading("customer_phone", text="رقم الهاتف")
        results_tree.heading("device_type", text="نوع الجهاز")
        results_tree.heading("serial_number", text="الرقم التسلسلي")
        results_tree.heading("status", text="الحالة")
        results_tree.heading("price", text="السعر")
        results_tree.heading("payment", text="الدفع")
        results_tree.heading("received_date", text="تاريخ الاستلام")
        
        # تكوين عرض الأعمدة
        results_tree.column("#0", width=0, stretch=tk.NO)
        results_tree.column("id", width=50, anchor=tk.CENTER)
        results_tree.column("tracking_code", width=120, anchor=tk.CENTER)
        results_tree.column("customer_name", width=150, anchor=tk.CENTER)
        results_tree.column("customer_phone", width=110, anchor=tk.CENTER)
        results_tree.column("device_type", width=120, anchor=tk.CENTER)
        results_tree.column("serial_number", width=140, anchor=tk.CENTER)
        results_tree.column("status", width=100, anchor=tk.CENTER)
        results_tree.column("price", width=90, anchor=tk.CENTER)
        results_tree.column("payment", width=90, anchor=tk.CENTER)
        results_tree.column("received_date", width=110, anchor=tk.CENTER)
        
        # إضافة الشريط التمرير
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
        results_tree.configure(yscroll=scrollbar.set)
        
        # إضافة البيانات
        for job in jobs:
            # ترجمة الحالة
            arabic_status = self.translate_status_to_arabic(job['status'])
            
            # تحديد حالة الدفع
            payment_status = job.get('payment_status', 'unpaid')
            payment_method = job.get('payment_method', '')
            
            if payment_status == 'paid':
                if payment_method == 'cash':
                    payment_display = "💵 كاش"
                elif payment_method == 'wish_money':
                    payment_display = "💳 Wish"
                else:
                    payment_display = "✅ مدفوع"
            else:
                payment_display = "📝 دين"
            
            # تحديد السعر
            price_display = f"{job.get('final_cost', 0):.2f} $" if job.get('final_cost') else "غير محدد"
            
            # معالجة الرقم التسلسلي
            serial_number = job.get('serial_number', 'غير محدد')
            if serial_number is None:
                serial_number = 'غير محدد'
            
            results_tree.insert("", tk.END, values=(
                job['id'],
                job['tracking_code'],
                job['customer_name'],
                job['customer_phone'],
                job['device_type'],
                serial_number,
                arabic_status,
                price_display,
                payment_display,
                job['received_at'].strftime('%Y-%m-%d') if job['received_at'] else ''
            ))
        
        # زر إغلاق
        def close_window():
            results_window.destroy()
        
        # تعريف دالة النقر المزدوج
        def on_item_double_click(event):
            item = results_tree.selection()[0] if results_tree.selection() else None
            if item:
                values = results_tree.item(item, 'values')
                job_id = values[0]  # معرف الطلب
                results_window.destroy()
                # فتح نافذة التعديل
                self.edit_maintenance_with_id(job_id)
        
        results_tree.bind("<Double-1>", on_item_double_click)
        
        # تعبئة الواجهة
        results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # إطار الأزرار
        buttons_frame = ctk.CTkFrame(results_window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkButton(
            buttons_frame,
            text="إغلاق",
            command=close_window,
            width=200,
            height=40,
            fg_color="#757575",
            hover_color="#616161",
            font=("Arial", 14)
        ).pack(pady=10)
    def show_edit_dialog_with_job(self, job):
        """عرض نافذة التعديل باستخدام بيانات الطلب مباشرة"""
        # إنشاء نافذة التعديل
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"تعديل طلب الصيانة #{job['tracking_code']}")
        dialog.geometry("700x600")
        dialog.grab_set()
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # محتوى النافذة
        content = ctk.CTkScrollableFrame(dialog)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)
        
        # تبويبات التعديل - تصميم ملون وجذاب
        tabview = ctk.CTkTabview(content, 
                               fg_color=("#f0f0f0", "#2b2b2b"))
        tabview.pack(fill=tk.BOTH, expand=True, pady=(0, 1))
        
        # تبويبات التعديل - حالة الطلب أولاً
        tab_status = tabview.add("حالة الطلب")
        tab_info = tabview.add("المعلومات الأساسية")
        tab_parts = tabview.add("قطع الغيار")
        tab_payments = tabview.add("المدفوعات")
        
        # تعبئة التبويبات - حالة الطلب أولاً
        # نستخدم قاموس لتخزين مراجع الحقول
        form_fields = {}
        
        # تعبئة تبويب حالة الطلب أولاً
        self.setup_status_tab(tab_status, job)
        
        # تعبئة تبويب المعلومات الأساسية
        # تعريف دالة الحفظ قبل إعداد التبويب
        def save_changes():
            try:
                # جمع البيانات من حقول النموذج
                customer_name = form_fields['customer_entry'].get().strip()
                phone = form_fields['phone_entry'].get().strip()
                email = form_fields['email_entry'].get().strip()
                address = form_fields['address_entry'].get().strip()
                device_type = form_fields['device_type_combo'].get()
                model = form_fields['model_entry'].get().strip()
                serial = form_fields['serial_entry'].get().strip()
                issue = form_fields['issue_text'].get("1.0", tk.END).strip()
                notes = form_fields['notes_text'].get("1.0", tk.END).strip()
                
                # التحقق من البيانات المطلوبة
                if not customer_name or not phone:
                    messagebox.showwarning("تحذير", "الرجاء إدخال اسم العميل ورقم الهاتف")
                    return
                
                # تحديث بيانات العميل
                if not hasattr(self, 'maintenance_service'):
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    return
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
                if not hasattr(self, 'maintenance_service'):
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    return
                success, message = self.maintenance_service.update_maintenance_job(
                    job_id=job['id'],
                    device_type=device_type,
                    device_model=model if model else None,
                    serial_number=serial if serial else None,
                    issue_description=issue,
                    notes=notes if notes else None
                )
                
                if success:
                    messagebox.showinfo("نجاح", "✅ تم حفظ التغييرات بنجاح")
                    dialog.destroy()
                    self.load_data()
                else:
                    messagebox.showerror("خطأ", f"❌ فشل في تحديث بيانات الصيانة: {message}")
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"❌ حدث خطأ غير متوقع: {str(e)}")
        
        # تعبئة تبويب المعلومات الأساسية
        self.setup_edit_info_tab(tab_info, job, form_fields, save_changes)
        
        # تعبئة تبويب قطع الغيار
        self.setup_parts_tab(tab_parts, job)
        
        # تعبئة تبويب المدفوعات
        self.setup_payments_tab(tab_payments, job)
    
    def edit_maintenance_with_id(self, job_id):
        """فتح نافذة التعديل مع معرف الطلب"""
        # حفظ الطلب المحدد للتحرير
        if not hasattr(self, 'tree'):
            return
        
        # البحث عن الطلب في الجدول
        found = False
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if len(values) > 1 and str(values[1]) == str(job_id):
                # حفظ المحدد مؤقتاً
                self.tree.selection_set(item)
                found = True
                break
        
        if not found:
            # إذا لم يُعثر عليه في الجدول، دعنا نجد الطلب في قاعدة البيانات ونفتح نافذة التعديل مباشرة
            try:
                success, message, job = self.maintenance_service.get_job_details(job_id)
                if success:
                    # فتح نافذة التعديل مباشرة باستخدام بيانات الطلب
                    self.show_edit_dialog_with_job(job)
                else:
                    messagebox.showerror("خطأ", f"لم يتم العثور على الطلب: {message}")
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ: {str(e)}")
        else:
            # فتح نافذة التعديل
            self.edit_maintenance()
    
    def clear_search(self):
        """مسح حقل البحث وإعادة تحميل جميع البيانات"""
        if hasattr(self, 'search_var'):
            self.search_var.set("")
        # إلغاء الفلترة
        self.current_filter_status = None
        self._filter_mode_active = False  # تتبع حالة وضع الفلترة
        # إلغاء وضع الفلترة
        self._filter_mode_active = False
        # إعادة تحميل البيانات
        self.load_data()
        # إعادة تشغيل التحديث التلقائي إذا كان مفعّل
        if self.auto_refresh_enabled and self.auto_refresh_job is None:
            self.start_auto_refresh()
    
    def clear_status_filter(self):
        """إلغاء أي فلترة نشطة والعودة لعرض جميع الطلبات"""
        self.current_filter_status = None
        self._filter_mode_active = False
        # استعادة التحديث التلقائي إذا كان مفعّلاً
        if self.auto_refresh_enabled and self.auto_refresh_job is None:
            self.start_auto_refresh()
        # إعادة تحميل البيانات
        self.load_data()
    
    def filter_by_status_from_stats(self, status):
        """فلترة الطلبات حسب الحالة عند النقر على بطاقة الإحصائيات"""
        # لا نحتاج الانتقال إلى تبويب معين لأن القائمة في الإطار الرئيسي
        
        # إذا تم اختيار إجمالي الطلبات أو تم النقر خارج البطاقات، أعد ضبط الفلاتر
        if status is None:
            self.clear_status_filter()
            return
        
        # حفظ حالة الفلتر الحالية
        self.current_filter_status = status
        
        # عند وجود فلتر يجب إيقاف التحديث التلقائي مؤقتاً
        if status:
            # إيقاف التحديث التلقائي بشكل كامل أثناء الفلترة
            # إلغاء أي تحديثات مجدولة حالياً
            if self.auto_refresh_job:
                try:
                    self.after_cancel(self.auto_refresh_job)
                except:
                    pass
                self.auto_refresh_job = None
            
            self._filter_mode_active = True
        else:
            self._filter_mode_active = False
        
        # تطبيق الفلترة
        if not hasattr(self, 'tree'):
            return
        
        # مسح العرض الحالي
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # جلب البيانات من الخدمة
        if not hasattr(self, 'maintenance_service'):
            return
        
        try:
            # جلب البيانات مع الفلترة مباشرة من قاعدة البيانات
            # إزالة الـ limit للحصول على جميع النتائج عند الفلترة
            if status:
                # عند الفلترة حسب الحالة، نريد جلب جميع النتائج
                success, message, jobs = self.maintenance_service.search_jobs(
                    status=status,
                    limit=10000  # عدد كبير جداً لجلب جميع النتائج
                )
            else:
                # عند عدم وجود فلترة، جلب جميع النتائج
                success, message, jobs = self.maintenance_service.search_jobs(limit=10000)
            
            if not success:
                messagebox.showerror("خطأ", f"فشل في جلب البيانات: {message}")
                return
                
            if not jobs or len(jobs) == 0:
                message_status = self.translate_status_to_arabic(status) if status else "المحددة"
                messagebox.showinfo("لا توجد نتائج", f"لا توجد طلبات بالحالة: {message_status}")
                if hasattr(self, 'status_count'):
                    self.status_count.configure(text=f"{self.format_number_english(0)} عنصر")
                return
            
            filtered_jobs = jobs
            
            # إضافة البيانات المفلترة إلى الجدول
            for job in filtered_jobs:
                if hasattr(self, 'tree'):
                    # ترجمة الحالة إلى العربية
                    arabic_status = self.translate_status_to_arabic(job['status'])
                    
                    # تحديد حالة الدفع
                    payment_status = job.get('payment_status', 'unpaid')
                    payment_method = job.get('payment_method', '')
                    
                    if payment_status == 'paid':
                        if payment_method == 'cash':
                            payment_display = "💵 كاش"
                        elif payment_method == 'wish_money':
                            payment_display = "💳 Wish"
                        else:
                            payment_display = "✅ مدفوع"
                    else:
                        payment_display = "📝 دين"
                    
                    # تحديد السعر
                    price_display = f"{job.get('final_cost', 0):.2f} $" if job.get('final_cost') else "غير محدد"
                    
                    # معالجة الرقم التسلسلي
                    serial_number = job.get('serial_number', 'غير محدد')
                    if serial_number is None:
                        serial_number = 'غير محدد'
                    
                    # معالجة تاريخ التسليم
                    delivered_date = ''
                    if job.get('delivered_at'):
                        delivered_date = job['delivered_at'].strftime('%Y-%m-%d') if hasattr(job['delivered_at'], 'strftime') else str(job['delivered_at'])[:10]
                    
                    self.tree.insert("", tk.END, values=(
                        "☐",  # مربع التحديد (غير محدد)
                        job['id'],
                        job['tracking_code'],
                        job['customer_name'],
                        job['customer_phone'],
                        job['device_type'],
                        serial_number,
                        arabic_status,
                        price_display,
                        payment_display,
                        job['received_at'].strftime('%Y-%m-%d') if job['received_at'] else '',
                        delivered_date
                    ))
            
            # تحديث العداد
            if hasattr(self, 'status_count'):
                status_label = "جميع الطلبات" if not status else self.translate_status_to_arabic(status)
                self.status_count.configure(text=f"{self.format_number_english(len(filtered_jobs))} عنصر ({status_label})")
            
            # تسجيل عدد العناصر المجلوبة
            print(f"✅ تم جلب {len(filtered_jobs)} عنصر من الحالة '{status}' (الفلتر: {status})")
        
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ أثناء الفلترة: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def start_auto_refresh(self):
        """بدء التحديث التلقائي"""
        if self.auto_refresh_enabled and self.auto_refresh_job is None:
            self.auto_refresh()
    
    def stop_auto_refresh(self):
        """إيقاف التحديث التلقائي"""
        if self.auto_refresh_job:
            self.after_cancel(self.auto_refresh_job)
            self.auto_refresh_job = None
    
    def toggle_auto_refresh(self):
        """تبديل حالة التحديث التلقائي"""
        self.auto_refresh_enabled = not self.auto_refresh_enabled
        
        if self.auto_refresh_enabled:
            self.btn_auto_refresh.configure(fg_color="#4CAF50", hover_color="#45a049")
            self.auto_refresh_label.configure(text="🟢 التحديث التلقائي مفعّل", text_color="#4CAF50")
            self.start_auto_refresh()
            messagebox.showinfo("تم التفعيل", "✅ التحديث التلقائي مفعّل الآن\nسيتم تحديث القائمة كل 5 ثوانٍ")
        else:
            self.btn_auto_refresh.configure(fg_color="#757575", hover_color="#616161")
            self.auto_refresh_label.configure(text="🔴 التحديث التلقائي متوقف", text_color="#f44336")
            self.stop_auto_refresh()
            messagebox.showinfo("تم الإيقاف", "⏸️ تم إيقاف التحديث التلقائي")
    
    def auto_refresh(self):
        """التحديث التلقائي الدوري - محسّن"""
        if self.auto_refresh_enabled:
            # إذا كان هناك فلتر نشط أو وضع الفلترة مفعّل، لا تقم بأي تحديث
            if (hasattr(self, '_filter_mode_active') and self._filter_mode_active) or \
               (hasattr(self, 'current_filter_status') and self.current_filter_status is not None):
                # إيقاف التحديث التلقائي تماماً - لا جدولة للمستقبل
                self.auto_refresh_job = None
                print("⏸️ التحديث التلقائي متوقف بسبب الفلترة النشطة")
                return
            
            try:
                # حفظ الموضع الحالي للتمرير والعناصر المحددة
                if hasattr(self, 'tree'):
                    current_yview = self.tree.yview()
                    selected_items = self.tree.selection()
                    selected_ids = []
                    for item in selected_items:
                        try:
                            # الحصول على job_id من العمود الثاني (index 1)
                            job_id = self.tree.item(item)['values'][1]
                            selected_ids.append(job_id)
                        except:
                            pass
                else:
                    current_yview = None
                    selected_ids = []
                
                # تحديث البيانات بصمت (بدون رسائل)
                self.load_data(silent=True)
                
                # استعادة التحديد
                if hasattr(self, 'tree') and selected_ids:
                    for item in self.tree.get_children():
                        try:
                            values = self.tree.item(item)['values']
                            if len(values) > 1 and values[1] in selected_ids:
                                self.tree.selection_add(item)
                        except:
                            pass
                
                # استعادة موضع التمرير
                if hasattr(self, 'tree') and current_yview:
                    try:
                        self.tree.yview_moveto(current_yview[0])
                    except:
                        pass
                
                # تحديث وقت آخر تحديث
                self.last_refresh_time = datetime.now()
                
            except Exception as e:
                print(f"خطأ في التحديث التلقائي: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # جدولة التحديث التالي
                if self.auto_refresh_enabled:
                    self.auto_refresh_job = self.after(self.auto_refresh_interval, self.auto_refresh)
    
    def manual_refresh(self):
        """التحديث اليدوي"""
        # إذا كان هناك فلتر نشط، إلغاؤه أولاً
        if hasattr(self, '_filter_mode_active') and self._filter_mode_active:
            self.current_filter_status = None
            self._filter_mode_active = False
        self.load_data()
        messagebox.showinfo("تم التحديث", "✅ تم تحديث قائمة الطلبات بنجاح!")
        # إعادة تشغيل التحديث التلقائي إذا كان مفعّل
        if self.auto_refresh_enabled and self.auto_refresh_job is None:
            self.start_auto_refresh()
    
    def on_item_click(self, event):
        """معالجة حدث النقر على عنصر في الجدول"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        
        # تحديد العمود الذي تم النقر عليه
        column = self.tree.identify_column(event.x)
        
        # إذا كان النقر على عمود التحديد (العمود الأول)
        if column == "#1":  # عمود التحديد
            values = list(self.tree.item(item, 'values'))
            if values and len(values) > 0:
                if values[0] == "☐":  # إذا كان غير محدد
                    values[0] = "☑"  # تحديد
                else:  # إذا كان محدد
                    values[0] = "☐"  # إلغاء التحديد
                self.tree.item(item, values=values)
                
                # تحديث حالة مربع التحديد الرئيسي في رأس العمود
                self.update_header_checkbox()
    
    def on_item_double_click(self, event):
        """معالجة حدث النقر المزدوج على عنصر في الجدول"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        
        # تحديد العمود الذي تم النقر عليه
        column = self.tree.identify_column(event.x)
        
        # إذا كان النقر المزدوج على عمود السعر (العمود التاسع)
        if column == "#9":  # عمود السعر
            self.edit_price_inline(item)
        else:
            # النقر المزدوج العادي يفتح نافذة التعديل
            self.edit_maintenance()
    
    def edit_price_inline(self, item):
        """تعديل السعر مباشرة في الجدول مع إمكانية تغيير العملة"""
        values = list(self.tree.item(item, 'values'))
        if len(values) < 9:
            return
        
        job_id = values[1]  # معرف الطلب
        current_price = values[8]  # السعر الحالي
        
        # إزالة الرمز $ إذا كان موجوداً
        if current_price and current_price != "غير محدد":
            try:
                current_price = current_price.replace(" $", "").replace("$", "")
            except:
                current_price = ""
        
        # إنشاء نافذة صغيرة لتعديل السعر مع تغيير العملة
        dialog = ctk.CTkToplevel(self)
        dialog.title("تعديل السعر")
        dialog.geometry("400x250")
        dialog.grab_set()
        
        # مركز النافذة
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (250 // 2)
        dialog.geometry(f"400x250+{x}+{y}")
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # العنوان
        ctk.CTkLabel(dialog, text="تعديل السعر", font=("Arial", 16, "bold")).pack(pady=(10, 20))
        
        # إطار العملة والسعر
        price_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        price_frame.pack(pady=10, padx=20, fill="x")
        
        # اختيار العملة
        ctk.CTkLabel(price_frame, text="العملة:", font=("Arial", 12)).pack(anchor="w")
        currency_frame = ctk.CTkFrame(price_frame, fg_color="transparent")
        currency_frame.pack(fill="x", pady=(5, 10))
        
        currency_var = tk.StringVar(value="USD")
        usd_radio = ctk.CTkRadioButton(currency_frame, text="💵 دولار ($)", variable=currency_var, value="USD")
        usd_radio.pack(side=tk.LEFT, padx=(0, 20))
        
        lbp_radio = ctk.CTkRadioButton(currency_frame, text="💱 ليرة لبنانية (ل.ل)", variable=currency_var, value="LBP")
        lbp_radio.pack(side=tk.LEFT)
        
        # حقل السعر
        ctk.CTkLabel(price_frame, text="السعر:", font=("Arial", 12)).pack(anchor="w")
        price_entry = ctk.CTkEntry(price_frame, width=300, placeholder_text="أدخل السعر", font=("Arial", 12))
        if current_price:
            price_entry.insert(0, current_price)
        price_entry.pack(pady=(5, 10))
        price_entry.focus()
        
        # عرض التحويل
        conversion_label = ctk.CTkLabel(price_frame, text="", font=("Arial", 10), text_color="#666666")
        conversion_label.pack(pady=(0, 10))
        
        def update_conversion():
            """تحديث عرض التحويل"""
            try:
                amount = float(price_entry.get()) if price_entry.get() else 0
                currency = currency_var.get()
                
                if amount > 0:
                    if currency == "USD":
                        lbp_amount = amount * 90000  # سعر الصرف
                        conversion_label.configure(text=f"المبلغ بالليرة: {lbp_amount:,.0f} ل.ل")
                    else:
                        usd_amount = amount / 90000  # سعر الصرف
                        conversion_label.configure(text=f"المبلغ بالدولار: ${usd_amount:.2f}")
                else:
                    conversion_label.configure(text="")
            except ValueError:
                conversion_label.configure(text="")
        
        # ربط التحديثات
        price_entry.bind('<KeyRelease>', lambda e: update_conversion())
        currency_var.trace('w', lambda *args: update_conversion())
        
        # تحديث التحويل عند فتح النافذة
        update_conversion()
        
        def save_price():
            try:
                new_price = price_entry.get().strip()
                if not new_price:
                    messagebox.showwarning("تحذير", "الرجاء إدخال سعر")
                    return
                
                price_float = float(new_price)
                currency = currency_var.get()
                
                # تحويل السعر إلى الدولار إذا كان بالليرة اللبنانية
                if currency == "LBP":
                    price_float = price_float / 90000  # تحويل إلى دولار
                
                # تحديث السعر في قاعدة البيانات
                if hasattr(self, 'maintenance_service'):
                    success, message = self.maintenance_service.update_maintenance_job(
                        job_id=int(job_id),
                        final_cost=price_float
                    )
                    
                    if success:
                        # تحديث السعر في الجدول (يعرض بالدولار دائماً)
                        values[8] = f"{price_float:.2f} $"
                        self.tree.item(item, values=values)
                        messagebox.showinfo("نجح", f"تم تحديث السعر بنجاح!\nالسعر النهائي: ${price_float:.2f}")
                        dialog.destroy()
                    else:
                        messagebox.showerror("خطأ", f"فشل في تحديث السعر: {message}")
                else:
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة")
                    
            except ValueError:
                messagebox.showerror("خطأ", "الرجاء إدخال رقم صحيح")
            except Exception as e:
                messagebox.showerror("خطأ", f"حدث خطأ: {str(e)}")
        
        # أزرار التحكم
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="💾 حفظ", command=save_price, 
                     fg_color="#4CAF50", hover_color="#45a049", width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(btn_frame, text="❌ إلغاء", command=dialog.destroy,
                     fg_color="#757575", hover_color="#616161", width=100).pack(side=tk.LEFT, padx=5)
        
        # ربط Enter بحفظ السعر
        price_entry.bind('<Return>', lambda e: save_price())
    
    def select_all_items(self):
        """تحديد جميع العناصر في الجدول"""
        if not hasattr(self, 'tree'):
            return
        
        for item in self.tree.get_children():
            values = list(self.tree.item(item, 'values'))
            if values and values[0] == "☐":  # إذا كان غير محدد
                values[0] = "☑"  # تحديد
                self.tree.item(item, values=values)
    
    def deselect_all_items(self):
        """إلغاء تحديد جميع العناصر في الجدول"""
        if not hasattr(self, 'tree'):
            return
        
        for item in self.tree.get_children():
            values = list(self.tree.item(item, 'values'))
            if values and values[0] == "☑":  # إذا كان محدد
                values[0] = "☐"  # إلغاء التحديد
                self.tree.item(item, values=values)
    
    def toggle_select_all(self):
        """تبديل تحديد/إلغاء تحديد جميع العناصر"""
        if not hasattr(self, 'tree'):
            return
        
        # التحقق من الحالة الحالية: هل كل العناصر محددة؟
        all_selected = True
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values and values[0] == "☐":  # وجدنا عنصر غير محدد
                all_selected = False
                break
        
        # إذا كانت كلها محددة، ألغِ التحديد. وإلا حدد الكل
        if all_selected:
            # إلغاء تحديد الكل
            for item in self.tree.get_children():
                values = list(self.tree.item(item, 'values'))
                if values:
                    values[0] = "☐"
                    self.tree.item(item, values=values)
            # تحديث رأس العمود
            self.tree.heading("select", text="☐")
            self.all_selected = False
        else:
            # تحديد الكل
            for item in self.tree.get_children():
                values = list(self.tree.item(item, 'values'))
                if values:
                    values[0] = "☑"
                    self.tree.item(item, values=values)
            # تحديث رأس العمود
            self.tree.heading("select", text="☑")
            self.all_selected = True
    
    def update_header_checkbox(self):
        """تحديث حالة مربع التحديد في رأس العمود"""
        if not hasattr(self, 'tree'):
            return
        
        # التحقق من حالة جميع العناصر
        all_selected = True
        any_selected = False
        
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values:
                if values[0] == "☑":
                    any_selected = True
                else:
                    all_selected = False
        
        # تحديث رأس العمود بناءً على الحالة
        if all_selected and any_selected:
            self.tree.heading("select", text="☑")  # كل العناصر محددة
        else:
            self.tree.heading("select", text="☐")  # بعض أو لا شيء محدد
    
    def smart_delete(self):
        """حذف ذكي: يحذف العناصر المحددة إذا وُجدت، وإلا يحذف الصف الحالي"""
        if not hasattr(self, 'tree'):
            return
        
        # البحث عن العناصر المحددة
        selected_items = []
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values and values[0] == "☑":  # إذا كان محدد
                selected_items.append((item, values[1]))  # (TreeView item, ID العنصر)
        
        # إذا وُجدت عناصر محددة، احذفها
        if selected_items:
            # تأكيد الحذف
            if not messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من حذف {len(selected_items)} عنصر؟"):
                return
            
            try:
                deleted_count = 0
                for tree_item, item_id in selected_items:
                    if hasattr(self, 'maintenance_service'):
                        success, message = self.maintenance_service.delete_job(item_id)
                        if success:
                            deleted_count += 1
                
                if deleted_count > 0:
                    messagebox.showinfo("نجاح", f"✅ تم حذف {deleted_count} عنصر بنجاح")
                    self.load_data()  # تحديث الجدول
                else:
                    messagebox.showerror("خطأ", "❌ فشل في حذف العناصر")
                    
            except Exception as e:
                messagebox.showerror("خطأ", f"❌ حدث خطأ غير متوقع: {str(e)}")
        else:
            # إذا لم توجد عناصر محددة، احذف الصف الحالي (السلوك القديم)
            self.delete_maintenance()
    
    def delete_selected_items(self):
        """حذف العناصر المحددة"""
        if not hasattr(self, 'tree'):
            return
        
        selected_items = []
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values and values[0] == "☑":  # إذا كان محدد
                selected_items.append(values[1])  # ID العنصر
        
        if not selected_items:
            messagebox.showwarning("تحذير", "الرجاء تحديد عنصر واحد على الأقل للحذف")
            return
        
        # تأكيد الحذف
        if not messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من حذف {len(selected_items)} عنصر؟"):
            return
        
        try:
            deleted_count = 0
            for item_id in selected_items:
                if hasattr(self, 'maintenance_service'):
                    success, message = self.maintenance_service.delete_job(item_id)
                    if success:
                        deleted_count += 1
            
            if deleted_count > 0:
                messagebox.showinfo("نجاح", f"تم حذف {deleted_count} عنصر بنجاح")
                self.load_data()  # تحديث الجدول
            else:
                messagebox.showerror("خطأ", "فشل في حذف العناصر")
                
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ غير متوقع: {str(e)}")
    
    def generate_orders_report(self):
        """إنشاء تقرير بالطلبات"""
        if hasattr(self, 'report_text'):
            self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, "تقرير طلبات الصيانة\n")
        self.report_text.insert(tk.END, "=" * 50 + "\n\n")
        
        # جلب بيانات الطلبات
        success, message, jobs = self.maintenance_service.search_jobs()
        
        if success:
            for job in jobs:
                if hasattr(self, 'report_text'):
                    self.report_text.insert(tk.END, f"رقم الطلب: {job['tracking_code']}\n")
                self.report_text.insert(tk.END, f"العميل: {job['customer_name']}\n")
                self.report_text.insert(tk.END, f"الجهاز: {job['device_type']} - {job.get('device_model', '')}\n")
                self.report_text.insert(tk.END, f"الحالة: {job['status']}\n")
                self.report_text.insert(tk.END, f"تاريخ الاستلام: {job['received_at'].strftime('%Y-%m-%d') if job['received_at'] else ''}\n")
                self.report_text.insert(tk.END, "-" * 50 + "\n\n")
            
            if hasattr(self, 'status_label'):
                self.status_label.configure(text=f"تم إنشاء التقرير - {self.format_number_english(len(jobs))} طلب")
        else:
            messagebox.showerror("خطأ", f"فشل في إنشاء التقرير: {message}")
    
    def generate_payments_report(self):
        """إنشاء تقرير بالمدفوعات (قديم - محفوظ للتوافق)"""
        pass
    
    def on_report_type_changed(self, value=None):
        """معالجة تغيير نوع التقرير"""
        report_type = self.report_type_var.get()
        if report_type == "custom":
            self.custom_date_frame.grid()
        else:
            self.custom_date_frame.grid_remove()
        # تحديث التقرير تلقائياً عند تغيير نوع التقرير
        self.on_filter_changed()
    
    def on_filter_changed(self, value=None):
        """معالجة تغيير أي فلتر - تحديث التقرير تلقائياً"""
        # التأكد من أن العناصر جاهزة
        if not hasattr(self, 'report_type_var') or not hasattr(self, 'code_type_var') or not hasattr(self, 'status_filter_var'):
            return
        
        # التأكد من أن maintenance_service موجود
        if not hasattr(self, 'maintenance_service') or self.maintenance_service is None:
            return
        
        # تحديث التقرير تلقائياً (silent mode - بدون رسائل خطأ مزعجة)
        try:
            self.generate_advanced_report(silent=True)
        except Exception as e:
            # في حالة الخطأ، لا نعرض رسالة خطأ لأن هذا تحديث تلقائي
            print(f"خطأ في التحديث التلقائي: {e}")
    
    def generate_advanced_report(self, silent=False):
        """إنشاء تقرير متقدم"""
        try:
            # التحقق من وجود العناصر
            if not hasattr(self, 'report_type_var') or not hasattr(self, 'code_type_var') or not hasattr(self, 'status_filter_var'):
                if not silent:
                    messagebox.showwarning("تحذير", "عناصر الواجهة غير جاهزة. يرجى المحاولة مرة أخرى.")
                return
            
            if not hasattr(self, 'maintenance_service') or self.maintenance_service is None:
                if not silent:
                    messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة.")
                return
            
            # جمع المعاملات
            report_type = self.report_type_var.get()
            if report_type == "monthly" and not self.monthly_stats_enabled:
                report_type = "weekly"
                self.report_type_var.set(report_type)
            code_type = self.code_type_var.get()
            status = self.status_filter_var.get()
            
            # معالجة نوع الكود
            code_type_filter = None if code_type == "all" else code_type
            
            # معالجة الحالة
            status_filter = "delivered" if status == "delivered" else None
            
            # معالجة التواريخ المخصصة
            start_date = None
            end_date = None
            if report_type == "custom":
                if not hasattr(self, 'start_date_entry') or not hasattr(self, 'end_date_entry'):
                    if not silent:
                        messagebox.showwarning("تحذير", "حقول التاريخ غير متاحة.")
                    return
                start_str = self.start_date_entry.get().strip()
                end_str = self.end_date_entry.get().strip()
                if start_str and end_str:
                    try:
                        start_date = datetime.strptime(start_str, "%Y-%m-%d")
                        end_date = datetime.strptime(end_str, "%Y-%m-%d")
                    except ValueError:
                        if not silent:
                            messagebox.showerror("خطأ", "صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD")
                        return
                else:
                    if not silent:
                        messagebox.showwarning("تحذير", "الرجاء إدخال تاريخ البداية والنهاية")
                    return
            
            # جلب بيانات التقرير
            success, message, report_data = self.maintenance_service.get_report_data(
                report_type=report_type,
                code_type=code_type_filter,
                status=status_filter,
                start_date=start_date,
                end_date=end_date
            )
            
            if not success:
                if not silent:
                    messagebox.showerror("خطأ", f"فشل في جلب بيانات التقرير: {message}")
                return
            
            # حفظ بيانات التقرير
            self.current_report_data = report_data
            
            # عرض التقرير
            self.display_report(report_data)
            
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ أثناء إنشاء التقرير: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def display_report(self, report_data: Dict[str, Any]):
        """عرض التقرير في الواجهة"""
        try:
            # التحقق من وجود العناصر
            if not hasattr(self, 'summary_frame') or not hasattr(self, 'charts_container'):
                messagebox.showwarning("تحذير", "عناصر الواجهة غير جاهزة.")
                return
            
            # تحديث الملخص التنفيذي
            self.update_summary_frame(report_data)
            
            # تحديث الرسوم البيانية
            self.update_charts(report_data)
            
        except Exception as e:
            print(f"خطأ في عرض التقرير: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("خطأ", f"حدث خطأ أثناء عرض التقرير: {str(e)}")
    
    def update_summary_frame(self, report_data: Dict[str, Any]):
        """تحديث إطار الملخص التنفيذي"""
        if not hasattr(self, 'summary_frame'):
            return
        
        # مسح المحتوى السابق
        for widget in self.summary_frame.winfo_children():
            widget.destroy()
        
        # نوع التقرير
        report_type_labels = {
            'daily': 'يومي',
            'weekly': 'أسبوعي',
            'yearly': 'سنوي',
            'custom': 'مخصص'
        }
        if self.monthly_stats_enabled:
            report_type_labels['monthly'] = 'شهري'
        report_type_label = report_type_labels.get(report_data.get('report_type', ''), 'غير محدد')
        
        # العنوان
        title_text = f"📊 تقرير {report_type_label} - {report_data.get('code_type', 'جميع الأنواع')}"
        ctk.CTkLabel(
            self.summary_frame,
            text=title_text,
            font=("Arial", 16, "bold"),
            text_color="#1976D2"
        ).grid(row=0, column=0, columnspan=3, pady=10)
        
        # الإحصائيات الأساسية
        stats = [
            ("عدد الأجهزة", f"{report_data.get('total_jobs', 0)}", "#2196F3"),
            ("مجموع الدخل", f"${report_data.get('total_revenue', 0):.2f}", "#4CAF50"),
            ("مسلمة", f"{report_data.get('delivered_count', 0)}", "#9C27B0")
        ]
        
        for i, (label, value, color) in enumerate(stats):
            stat_frame = ctk.CTkFrame(self.summary_frame, fg_color=color, corner_radius=8)
            stat_frame.grid(row=1, column=i, padx=5, pady=5, sticky="ew")
            
            ctk.CTkLabel(
                stat_frame,
                text=value,
                font=("Arial", 18, "bold"),
                text_color="white"
            ).pack(pady=(10, 5))
            
            ctk.CTkLabel(
                stat_frame,
                text=label,
                font=("Arial", 11),
                text_color="white"
            ).pack(pady=(0, 10))
    
    def update_report_table(self, report_data: Dict[str, Any]):
        """تحديث جدول الطلبات - معطل (تم إزالة الجدول)"""
        # تم إزالة الجدول التفصيلي بناءً على طلب المستخدم
        pass
    
    def update_charts(self, report_data: Dict[str, Any]):
        """تحديث الرسوم البيانية"""
        if not hasattr(self, 'charts_container'):
            return
        
        # مسح المحتوى السابق
        for widget in self.charts_container.winfo_children():
            widget.destroy()
        
        try:
            # رسم بياني حسب نوع الجهاز
            device_stats = report_data.get('device_type_stats', {})
            if device_stats:
                self.create_device_type_chart(device_stats)
            
            # رسم بياني حسب طريقة الدفع
            payment_stats = report_data.get('payment_stats', {})
            if payment_stats:
                self.create_payment_chart(payment_stats)
                
        except Exception as e:
            print(f"خطأ في إنشاء الرسوم البيانية: {e}")
            # عرض نص بديل
            ctk.CTkLabel(
                self.charts_container,
                text="الرسوم البيانية غير متاحة\n(يتطلب تثبيت matplotlib)",
                font=("Arial", 12),
                text_color="#757575"
            ).pack(pady=20)
    
    def create_device_type_chart(self, device_stats: Dict[str, Dict]):
        """إنشاء رسم بياني لأنواع الأجهزة"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib
            matplotlib.use('TkAgg')
            
            # تحضير البيانات
            devices = list(device_stats.keys())
            counts = [device_stats[d]['count'] for d in devices]
            revenues = [device_stats[d]['revenue'] for d in devices]
            
            # إنشاء الرسم بحجم أكبر لملء الشاشة
            # استخدام حجم ثابت كبير لملء الشاشة
            # سيتم تكبيره تلقائياً بواسطة pack
            fig_width = 14
            fig_height = 10
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(fig_width, fig_height), dpi=100)
            fig.patch.set_facecolor('#2b2b2b')
            
            # رسم بياني للعدد
            ax1.bar(devices, counts, color=['#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#00BCD4'][:len(devices)])
            ax1.set_title('عدد الأجهزة حسب النوع', color='white', fontsize=14, fontweight='bold')
            ax1.set_facecolor('#2b2b2b')
            ax1.tick_params(colors='white', labelsize=11)
            ax1.set_xlabel('نوع الجهاز', color='white', fontsize=12)
            ax1.set_ylabel('العدد', color='white', fontsize=12)
            
            # رسم بياني للإيرادات
            ax2.bar(devices, revenues, color=['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#00BCD4'][:len(devices)])
            ax2.set_title('الإيرادات حسب النوع', color='white', fontsize=14, fontweight='bold')
            ax2.set_facecolor('#2b2b2b')
            ax2.tick_params(colors='white', labelsize=11)
            ax2.set_xlabel('نوع الجهاز', color='white', fontsize=12)
            ax2.set_ylabel('الإيرادات ($)', color='white', fontsize=12)
            
            plt.tight_layout(pad=2.0)
            
            # إضافة الرسم إلى الواجهة
            canvas = FigureCanvasTkAgg(fig, self.charts_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            
        except ImportError:
            # عرض نص بديل
            text = "أنواع الأجهزة:\n"
            for device, stats in device_stats.items():
                text += f"{device}: {stats['count']} جهاز - ${stats['revenue']:.2f}\n"
            ctk.CTkLabel(
                self.charts_container,
                text=text,
                font=("Arial", 10),
                justify="left"
            ).pack(pady=5)
        except Exception as e:
            print(f"خطأ في رسم بياني أنواع الأجهزة: {e}")
    
    def create_payment_chart(self, payment_stats: Dict[str, float]):
        """إنشاء رسم بياني لطرق الدفع"""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import matplotlib
            matplotlib.use('TkAgg')
            
            # تحضير البيانات
            methods = []
            values = []
            colors = []
            labels_ar = []
            
            if payment_stats.get('cash', 0) > 0:
                methods.append('cash')
                values.append(payment_stats['cash'])
                colors.append('#4CAF50')
                labels_ar.append('كاش')
            
            if payment_stats.get('wish_money', 0) > 0:
                methods.append('wish_money')
                values.append(payment_stats['wish_money'])
                colors.append('#2196F3')
                labels_ar.append('Wish Money')
            
            if payment_stats.get('unpaid', 0) > 0:
                methods.append('unpaid')
                values.append(payment_stats['unpaid'])
                colors.append('#F44336')
                labels_ar.append('دين')
            
            if not values:
                return
            
            # استخدام حجم ثابت كبير لملء الشاشة
            fig_size = 10
            
            # إنشاء رسم دائري بحجم أكبر
            fig, ax = plt.subplots(figsize=(fig_size, fig_size), dpi=100)
            fig.patch.set_facecolor('#2b2b2b')
            ax.set_facecolor('#2b2b2b')
            
            ax.pie(values, labels=labels_ar, colors=colors, autopct='%1.1f%%', 
                   textprops={'color': 'white', 'fontsize': 12, 'fontweight': 'bold'})
            ax.set_title('طرق الدفع', color='white', fontsize=16, fontweight='bold', pad=20)
            
            plt.tight_layout(pad=2.0)
            
            # إضافة الرسم إلى الواجهة
            canvas = FigureCanvasTkAgg(fig, self.charts_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            
        except ImportError:
            # عرض نص بديل
            text = "طرق الدفع:\n"
            if payment_stats.get('cash', 0) > 0:
                text += f"كاش: ${payment_stats['cash']:.2f}\n"
            if payment_stats.get('wish_money', 0) > 0:
                text += f"Wish Money: ${payment_stats['wish_money']:.2f}\n"
            if payment_stats.get('unpaid', 0) > 0:
                text += f"دين: ${payment_stats['unpaid']:.2f}\n"
            ctk.CTkLabel(
                self.charts_container,
                text=text,
                font=("Arial", 10),
                justify="left"
            ).pack(pady=5)
        except Exception as e:
            print(f"خطأ في رسم بياني طرق الدفع: {e}")
    
    def export_report_pdf(self):
        """تصدير التقرير كملف PDF"""
        if not self.current_report_data:
            messagebox.showwarning("تحذير", "لا يوجد تقرير للتصدير. يرجى إنشاء تقرير أولاً.")
            return
        
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
            )
            
            if filename:
                # هنا يمكن إضافة كود لإنشاء PDF باستخدام مكتبة مثل reportlab
                messagebox.showinfo("نجاح", f"سيتم تصدير التقرير إلى: {filename}\n(هذه الميزة تحتاج تثبيت مكتبة reportlab)")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تصدير PDF: {str(e)}")
    
    def export_report_excel(self):
        """تصدير التقرير كملف Excel"""
        if not self.current_report_data:
            messagebox.showwarning("تحذير", "لا يوجد تقرير للتصدير. يرجى إنشاء تقرير أولاً.")
            return
        
        try:
            from tkinter import filedialog
            import csv
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            
            if filename:
                report_data = self.current_report_data
                jobs = report_data.get('jobs', [])
                
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    # رأس الجدول
                    writer.writerow(['رقم التتبع', 'اسم العميل', 'هاتف العميل', 'نوع الجهاز', 'الحالة', 'السعر', 'طريقة الدفع', 'تاريخ الاستلام'])
                    
                    # البيانات
                    for job in jobs:
                        date_str = ""
                        if job.get('received_at'):
                            date_obj = job['received_at']
                            if hasattr(date_obj, 'strftime'):
                                date_str = date_obj.strftime('%Y-%m-%d')
                            else:
                                date_str = str(date_obj)[:10]
                        
                        payment_display = ""
                        if job.get('payment_status') == 'paid':
                            if job.get('payment_method') == 'cash':
                                payment_display = "كاش"
                            elif job.get('payment_method') == 'wish_money':
                                payment_display = "Wish Money"
                            else:
                                payment_display = "مدفوع"
                        else:
                            payment_display = "دين"
                        
                        writer.writerow([
                            job.get('tracking_code', ''),
                            job.get('customer_name', ''),
                            job.get('customer_phone', ''),
                            job.get('device_type', ''),
                            job.get('status', ''),
                            job.get('final_cost', 0),
                            payment_display,
                            date_str
                        ])
                
                messagebox.showinfo("نجاح", f"تم تصدير التقرير بنجاح إلى: {filename}")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تصدير Excel: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def print_report(self):
        """طباعة التقرير"""
        if not self.current_report_data:
            messagebox.showwarning("تحذير", "لا يوجد تقرير للطباعة. يرجى إنشاء تقرير أولاً.")
            return
        
        try:
            # إنشاء نافذة طباعة
            print_window = ctk.CTkToplevel(self)
            print_window.title("طباعة التقرير")
            print_window.geometry("800x600")
            
            # إطار المحتوى
            content_frame = ctk.CTkScrollableFrame(print_window)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            report_data = self.current_report_data
            
            # العنوان
            report_type_labels = {
                'daily': 'يومي',
                'weekly': 'أسبوعي',
                'yearly': 'سنوي',
                'custom': 'مخصص'
            }
            if self.monthly_stats_enabled:
                report_type_labels['monthly'] = 'شهري'
            title = f"تقرير {report_type_labels.get(report_data.get('report_type', ''), '')} - {report_data.get('code_type', 'جميع الأنواع')}"
            ctk.CTkLabel(
                content_frame,
                text=title,
                font=("Arial", 18, "bold")
            ).pack(pady=10)
            
            # الملخص
            summary_text = (
                f"عدد الأجهزة: {report_data.get('total_jobs', 0)}\n"
                f"مجموع الدخل: ${report_data.get('total_revenue', 0):.2f}\n"
                f"متوسط السعر: ${report_data.get('avg_price', 0):.2f}\n"
                f"الأجهزة المسلمة: {report_data.get('delivered_count', 0)}\n"
            )
            ctk.CTkLabel(
                content_frame,
                text=summary_text,
                font=("Arial", 12),
                justify="left"
            ).pack(pady=10)
            
            # الجدول
            table_text = "الطلبات:\n" + "="*80 + "\n"
            for job in report_data.get('jobs', [])[:50]:  # أول 50 طلب
                table_text += (
                    f"{job.get('tracking_code', '')} | "
                    f"{job.get('customer_name', '')} | "
                    f"{job.get('device_type', '')} | "
                    f"${job.get('final_cost', 0):.2f}\n"
                )
            
            text_widget = ctk.CTkTextbox(content_frame, width=750, height=400)
            text_widget.pack(pady=10)
            text_widget.insert("1.0", table_text)
            text_widget.configure(state="disabled")
            
            # أزرار
            buttons_frame = ctk.CTkFrame(print_window)
            buttons_frame.pack(fill=tk.X, padx=10, pady=10)
            
            def do_print():
                # هنا يمكن إضافة كود الطباعة الفعلية
                messagebox.showinfo("طباعة", "سيتم إرسال التقرير إلى الطابعة")
                print_window.destroy()
            
            ctk.CTkButton(
                buttons_frame,
                text="طباعة",
                command=do_print,
                width=150
            ).pack(side=tk.LEFT, padx=5)
            
            ctk.CTkButton(
                buttons_frame,
                text="إغلاق",
                command=print_window.destroy,
                width=150
            ).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في فتح نافذة الطباعة: {str(e)}")
    
    def show_auto_backup_window(self):
        """عرض نافذة النسخ الاحتياطي التلقائي"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("🔄 النسخ الاحتياطي التلقائي - ADR ELECTRONICS")
        dialog.geometry("700x500")
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(dialog)
        
        # مركز النافذة على الشاشة
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (dialog.winfo_screenheight() // 2) - (500 // 2)
        dialog.geometry(f"700x500+{x}+{y}")
        
        # عنوان النافذة
        title_frame = ctk.CTkFrame(dialog, fg_color="#FF5722", corner_radius=15)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkLabel(
            title_frame, 
            text="🔄 النسخ الاحتياطي التلقائي", 
            font=("Arial", 20, "bold"), 
            text_color="white"
        ).pack(pady=3)
        
        # محتوى النافذة
        content_frame = ctk.CTkScrollableFrame(dialog, fg_color="#fafafa", corner_radius=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # معلومات النسخ الاحتياطي التلقائي
        info_frame = ctk.CTkFrame(content_frame, fg_color="#fff3e0", corner_radius=10)
        info_frame.pack(fill=tk.X, pady=2, padx=10)
        
        ctk.CTkLabel(
            info_frame,
            text="📋 النسخ الاحتياطي التلقائي كل 30 دقيقة:",
            font=("Arial", 16, "bold"),
            text_color="#f57c00"
        ).pack(anchor=tk.W, padx=15, pady=(1, 1))
        
        info_text = """
• ⏰ نسخ احتياطي تلقائي كل 30 دقيقة
• 🗄️ نسخ احتياطي لقاعدة البيانات فقط (سريع)
• 📁 حفظ النسخ في مجلد backups/
• 🧹 تنظيف تلقائي للنسخ القديمة (أكثر من 7 أيام)
• 📊 سجلات مفصلة في مجلد logs/
• 🔄 يعمل في الخلفية بدون توقف
        """
        
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=("Arial", 12),
            text_color="#424242"
        ).pack(anchor=tk.W, padx=15, pady=(0, 1))
        
        # أزرار التحكم
        buttons_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        buttons_frame.pack(fill=tk.X, pady=10, padx=10)
        
        def start_auto_backup():
            """بدء النسخ الاحتياطي التلقائي"""
            try:
                from utils.auto_backup import start_auto_backup
                
                # بدء النسخ الاحتياطي التلقائي
                start_auto_backup(interval_minutes=30)
                
                messagebox.showinfo("نجاح", "تم بدء النسخ الاحتياطي التلقائي بنجاح!\nسيتم إنشاء نسخة احتياطية كل 30 دقيقة.")
                
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في بدء النسخ الاحتياطي التلقائي: {str(e)}")
        
        def stop_auto_backup():
            """إيقاف النسخ الاحتياطي التلقائي"""
            try:
                from utils.auto_backup import stop_auto_backup
                
                # إيقاف النسخ الاحتياطي التلقائي
                stop_auto_backup()
                
                messagebox.showinfo("نجاح", "تم إيقاف النسخ الاحتياطي التلقائي!")
                
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في إيقاف النسخ الاحتياطي التلقائي: {str(e)}")
        
        # زر بدء النسخ الاحتياطي التلقائي
        start_btn = ctk.CTkButton(
            buttons_frame,
            text="▶️ بدء النسخ التلقائي",
            command=start_auto_backup,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=180,
            height=45,
            font=("Arial", 12, "bold")
        )
        start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # زر إيقاف النسخ الاحتياطي التلقائي
        stop_btn = ctk.CTkButton(
            buttons_frame,
            text="⏹️ إيقاف النسخ التلقائي",
            command=stop_auto_backup,
            fg_color="#f44336",
            hover_color="#da190b",
            width=180,
            height=45,
            font=("Arial", 12, "bold")
        )
        stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # زر إغلاق
        close_btn = ctk.CTkButton(
            buttons_frame,
            text="❌ إغلاق",
            command=dialog.destroy,
            fg_color="#9E9E9E",
            hover_color="#757575",
            width=100,
            height=45,
            font=("Arial", 12, "bold")
        )
        close_btn.pack(side=tk.LEFT, padx=(10, 0))
    
    def show_cost_management_window(self):
        """عرض نافذة إدارة التكاليف والمصاريف"""
        messagebox.showinfo("تنبيه", "ميزة إدارة التكاليف غير متاحة حالياً.")
        return
        if not hasattr(self, 'maintenance_service'):
            messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة.")
            return

        if self.cost_manager_window and self.cost_manager_window.winfo_exists():
            self.cost_manager_window.focus()
            return

        self.cost_manager_window = ctk.CTkToplevel(self)
        window = self.cost_manager_window
        window.title("💸 إدارة تكاليف الأعطال - ADR ELECTRONICS")
        window.geometry("1100x650")
        window.grab_set()
        window.focus_force()
        window.protocol("WM_DELETE_WINDOW", self.close_cost_management_window)

        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(window)

        container = ctk.CTkFrame(window, fg_color="transparent")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # إطار قائمة الطلبات
        jobs_frame = ctk.CTkFrame(container, corner_radius=10)
        jobs_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))

        ctk.CTkLabel(
            jobs_frame,
            text="📋 طلبات الصيانة",
            font=("Arial", 15, "bold")
        ).pack(anchor=tk.W, padx=15, pady=(15, 5))

        jobs_toolbar = ctk.CTkFrame(jobs_frame, fg_color="transparent")
        jobs_toolbar.pack(fill=tk.X, padx=15, pady=(0, 10))

        ctk.CTkButton(
            jobs_toolbar,
            text="🔄 تحديث القائمة",
            command=self.refresh_cost_manager_jobs,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            height=36
        ).pack(side=tk.LEFT)

        ctk.CTkButton(
            jobs_toolbar,
            text="⬆️",
            width=40,
            fg_color="#B0BEC5",
            hover_color="#90A4AE",
            command=lambda: self.scroll_cost_jobs(-1)
        ).pack(side=tk.LEFT, padx=3)

        ctk.CTkButton(
            jobs_toolbar,
            text="⬇️",
            width=40,
            fg_color="#B0BEC5",
            hover_color="#90A4AE",
            command=lambda: self.scroll_cost_jobs(1)
        ).pack(side=tk.LEFT, padx=3)

        self.cost_jobs_tree = ttk.Treeview(
            jobs_frame,
            columns=("tracking", "customer", "status", "price", "net"),
            show="headings",
            height=20
        )
        self.cost_jobs_tree.heading("tracking", text="رقم التتبع")
        self.cost_jobs_tree.heading("customer", text="العميل")
        self.cost_jobs_tree.heading("status", text="الحالة")
        self.cost_jobs_tree.heading("price", text="السعر النهائي ($)")
        self.cost_jobs_tree.heading("net", text="صافي الربح ($)")

        self.cost_jobs_tree.column("tracking", width=110, anchor=tk.CENTER)
        self.cost_jobs_tree.column("customer", width=150)
        self.cost_jobs_tree.column("status", width=90, anchor=tk.CENTER)
        self.cost_jobs_tree.column("price", width=120, anchor=tk.E)
        self.cost_jobs_tree.column("net", width=120, anchor=tk.E)

        self.cost_jobs_tree.bind("<<TreeviewSelect>>", lambda _event: self.on_cost_manager_job_selected())

        jobs_scrollbar = ttk.Scrollbar(jobs_frame, orient=tk.VERTICAL, command=self.cost_jobs_tree.yview)
        self.cost_jobs_tree.configure(yscroll=jobs_scrollbar.set)
        self.cost_jobs_tree.pack(side=tk.LEFT, fill=tk.Y, padx=(15, 0), pady=(0, 15))
        jobs_scrollbar.pack(side=tk.LEFT, fill=tk.Y, pady=(0, 15))

        # إطار التفاصيل والمصاريف
        details_frame = ctk.CTkFrame(container, corner_radius=10)
        details_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.cost_job_info_label = ctk.CTkLabel(
            details_frame,
            text="يرجى اختيار طلب من القائمة لمتابعة التكاليف.",
            font=("Arial", 15, "bold"),
            justify=tk.LEFT
        )
        self.cost_job_info_label.pack(anchor=tk.W, padx=20, pady=(20, 10))

        summary_frame = ctk.CTkFrame(details_frame, fg_color="#F5F5F5", corner_radius=10)
        summary_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        self.cost_summary_labels = {
            "revenue": ctk.CTkLabel(summary_frame, text="الإيراد: --", font=("Arial", 13, "bold"), text_color="#1B5E20"),
            "expenses": ctk.CTkLabel(summary_frame, text="المصاريف: --", font=("Arial", 13, "bold"), text_color="#C62828"),
            "net": ctk.CTkLabel(summary_frame, text="صافي الربح: --", font=("Arial", 13, "bold"), text_color="#1565C0"),
            "currency": ctk.CTkLabel(summary_frame, text="العملة: USD", font=("Arial", 12))
        }

        summary_row = ctk.CTkFrame(summary_frame, fg_color="transparent")
        summary_row.pack(fill=tk.X, padx=15, pady=10)
        self.cost_summary_labels["revenue"].pack(in_=summary_row, side=tk.LEFT, padx=5)
        self.cost_summary_labels["expenses"].pack(in_=summary_row, side=tk.LEFT, padx=5)
        self.cost_summary_labels["net"].pack(in_=summary_row, side=tk.LEFT, padx=5)
        self.cost_summary_labels["currency"].pack(in_=summary_row, side=tk.RIGHT, padx=5)

        # جدول المصاريف
        expenses_container = ctk.CTkFrame(details_frame, corner_radius=10)
        expenses_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        ctk.CTkLabel(
            expenses_container,
            text="🧾 المصاريف المرتبطة بالطلب",
            font=("Arial", 14, "bold")
        ).pack(anchor=tk.W, padx=15, pady=(15, 5))

        tree_container = ctk.CTkFrame(expenses_container, fg_color="transparent")
        tree_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        self.cost_expenses_tree = ttk.Treeview(
            tree_container,
            columns=("description", "amount", "category", "included", "created"),
            show="headings",
            height=14
        )
        self.cost_expenses_tree.heading("description", text="الوصف")
        self.cost_expenses_tree.heading("amount", text="المبلغ ($)")
        self.cost_expenses_tree.heading("category", text="الفئة")
        self.cost_expenses_tree.heading("included", text="مضمن؟")
        self.cost_expenses_tree.heading("created", text="تاريخ الإضافة")

        self.cost_expenses_tree.column("description", width=260)
        self.cost_expenses_tree.column("amount", width=110, anchor=tk.E)
        self.cost_expenses_tree.column("category", width=120, anchor=tk.CENTER)
        self.cost_expenses_tree.column("included", width=80, anchor=tk.CENTER)
        self.cost_expenses_tree.column("created", width=120, anchor=tk.CENTER)

        self.cost_expenses_tree.tag_configure("excluded", foreground="#F44336")
        self.cost_expenses_tree.tag_configure("included", foreground="#1B5E20")
        self.cost_expenses_tree.bind("<<TreeviewSelect>>", lambda _event: self.on_cost_expense_selected())

        expenses_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.cost_expenses_tree.yview)
        self.cost_expenses_tree.configure(yscroll=expenses_scroll.set)
        self.cost_expenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        expenses_scroll.pack(side=tk.LEFT, fill=tk.Y)

        # نموذج إضافة/تحديث مصروف
        form_frame = ctk.CTkFrame(expenses_container, fg_color="#FAFAFA", corner_radius=10)
        form_frame.pack(fill=tk.X, padx=15, pady=(5, 15))

        ctk.CTkLabel(form_frame, text="إدارة المصروف:", font=("Arial", 13, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(12, 0))

        ctk.CTkLabel(form_frame, text="الوصف:", font=("Arial", 12)).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.cost_expense_description_entry = ctk.CTkEntry(form_frame, width=260, placeholder_text="مثال: تبديل Power Supply")
        self.cost_expense_description_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="المبلغ ($):", font=("Arial", 12)).grid(row=1, column=2, sticky="w", padx=10, pady=5)
        self.cost_expense_amount_entry = ctk.CTkEntry(form_frame, width=120, placeholder_text="0.00")
        self.cost_expense_amount_entry.grid(row=1, column=3, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(form_frame, text="الفئة:", font=("Arial", 12)).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.cost_expense_category_combo = ctk.CTkComboBox(
            form_frame,
            values=["قطع غيار", "هندسة", "شحن", "ضمان", "أخرى"],
            width=200
        )
        self.cost_expense_category_combo.set("قطع غيار")
        self.cost_expense_category_combo.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        self.cost_expense_include_switch = ctk.CTkSwitch(
            form_frame,
            text="تضمين في الربح",
            width=150
        )
        self.cost_expense_include_switch.select()
        self.cost_expense_include_switch.grid(row=2, column=2, columnspan=2, sticky="w", padx=10, pady=5)

        buttons_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        buttons_frame.grid(row=3, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 15))

        ctk.CTkButton(
            buttons_frame,
            text="➕ إضافة مصروف",
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self.add_cost_manager_expense
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="💾 تحديث المصروف",
            fg_color="#2196F3",
            hover_color="#1976D2",
            command=self.update_cost_manager_expense
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="🔄 تغيير حالة التضمين",
            fg_color="#FF9800",
            hover_color="#F57C00",
            command=self.toggle_cost_manager_expense_include
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="🗑️ حذف المصروف",
            fg_color="#E53935",
            hover_color="#C62828",
            command=self.delete_cost_manager_expense
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="💾 حفظ التحديثات",
            fg_color="#455A64",
            hover_color="#37474F",
            command=self.save_cost_manager_changes
        ).pack(side=tk.LEFT, padx=5)

        self.cost_jobs_map = {}
        self.cost_expenses_map = {}
        self.cost_manager_selected_job_id = None
        self.cost_selected_expense_id = None
        self.refresh_cost_manager_jobs()

    def close_cost_management_window(self):
        """إغلاق نافذة إدارة التكاليف"""
        if self.cost_manager_window and self.cost_manager_window.winfo_exists():
            self.cost_manager_window.destroy()
        self.cost_manager_window = None
        self.cost_jobs_tree = None
        self.cost_expenses_tree = None
        self.cost_jobs_map = {}
        self.cost_expenses_map = {}
        self.cost_manager_selected_job_id = None
        self.cost_selected_expense_id = None
        self.cost_expense_description_entry = None
        self.cost_expense_amount_entry = None
        self.cost_expense_category_combo = None
        self.cost_expense_include_switch = None
        self.cost_job_info_label = None
        self.cost_summary_labels = {}

    def refresh_cost_manager_jobs(self):
        """تحديث قائمة الطلبات في نافذة التكاليف"""
        if not hasattr(self, 'maintenance_service') or not getattr(self, 'cost_jobs_tree', None):
            return

        success, message, jobs = self.maintenance_service.search_jobs(limit=150)
        if not success:
            messagebox.showerror("خطأ", f"فشل في جلب الطلبات: {message}")
            return

        self.cost_jobs_tree.delete(*self.cost_jobs_tree.get_children())
        self.cost_jobs_map = {}

        for job in jobs:
            job_id = job["id"]
            tracking = job.get("tracking_code", "-")
            customer = job.get("customer_name") or "غير محدد"
            status = job.get("status") or "-"
            price = job.get("final_cost") or job.get("estimated_cost") or 0.0
            net_profit_text = "--"

            profit_success, _, profit_summary = self.maintenance_service.calculate_job_profit(job_id)
            if profit_success:
                net_profit_text = f"{profit_summary.get('net_profit', 0.0):.2f}"

            item_id = str(job_id)
            self.cost_jobs_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    tracking,
                    customer,
                    status,
                    f"{price:.2f}",
                    net_profit_text
                )
            )
            self.cost_jobs_map[item_id] = job_id

    def on_cost_manager_job_selected(self):
        """عند اختيار طلب من قائمة الطلبات"""
        if not getattr(self, 'cost_jobs_tree', None):
            return

        selection = self.cost_jobs_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        job_id = self.cost_jobs_map.get(item_id)
        if job_id:
            self.load_cost_manager_details(job_id)

    def load_cost_manager_details(self, job_id: int):
        """تحميل تفاصيل الطلب والمصاريف"""
        if not hasattr(self, 'maintenance_service'):
            return

        details_success, message, details = self.maintenance_service.get_job_details(job_id)
        if not details_success:
            messagebox.showerror("خطأ", f"فشل في جلب تفاصيل الطلب: {message}")
            return

        profit_success, message, summary = self.maintenance_service.calculate_job_profit(job_id)
        if not profit_success:
            messagebox.showerror("خطأ", f"فشل في حساب الربحية: {message}")
            return

        customer = details["customer"]["name"] if details.get("customer") else "غير محدد"
        device_type = details.get("device", {}).get("type") or "غير محدد"
        final_price = summary.get("revenue", 0.0)
        estimated_price = details.get("cost", {}).get("estimated") or 0.0

        info_text = (
            f"رقم التتبع: {details.get('tracking_code', '-')}\n"
            f"العميل: {customer}\n"
            f"نوع الجهاز: {device_type}\n"
            f"السعر النهائي: ${final_price:.2f} (التقديري: ${estimated_price:.2f})"
        )
        self.cost_job_info_label.configure(text=info_text)

        self.cost_summary_labels["revenue"].configure(text=f"الإيراد: ${summary.get('revenue', 0.0):.2f}")
        self.cost_summary_labels["expenses"].configure(text=f"المصاريف: ${summary.get('included_expenses', 0.0):.2f}")
        self.cost_summary_labels["net"].configure(text=f"صافي الربح: ${summary.get('net_profit', 0.0):.2f}")
        self.cost_summary_labels["currency"].configure(text=f"العملة: {summary.get('currency', 'USD')}")

        self.cost_expenses_tree.delete(*self.cost_expenses_tree.get_children())
        self.cost_expenses_map = {}

        for expense in summary.get("expenses", []):
            expense_id = expense.get("id")
            included = bool(expense.get("is_included"))
            tag = "included" if included else "excluded"
            amount = expense.get("amount", 0.0)
            created_at = expense.get("created_at")
            created_str = created_at.strftime("%Y-%m-%d") if created_at else "-"
            category = expense.get("category") or "أخرى"
            included_text = "نعم" if included else "لا"

            self.cost_expenses_tree.insert(
                "",
                tk.END,
                iid=str(expense_id),
                values=(
                    expense.get("description") or "-",
                    f"{amount:.2f}",
                    category,
                    included_text,
                    created_str
                ),
                tags=(tag,)
            )
            self.cost_expenses_map[str(expense_id)] = expense

        self.cost_manager_selected_job_id = job_id
        self.cost_selected_expense_id = None
        self.clear_cost_expense_form()

    def scroll_cost_jobs(self, direction: int):
        """زر للتمرير داخل قائمة الطلبات"""
        if getattr(self, 'cost_jobs_tree', None):
            try:
                self.cost_jobs_tree.yview_scroll(direction, "units")
            except Exception:
                pass

    def save_cost_manager_changes(self):
        """زر حفظ لإعادة تحميل البيانات والتأكيد"""
        job_id = self.cost_manager_selected_job_id
        if not job_id:
            messagebox.showwarning("تنبيه", "يرجى اختيار طلب قبل الحفظ.")
            return

        self.load_cost_manager_details(job_id)
        self.refresh_cost_manager_jobs()
        messagebox.showinfo("نجاح", "تم حفظ وتحديث بيانات الطلب والمصاريف.")

    def add_cost_manager_expense(self):
        """إضافة مصروف جديد"""
        job_id = self.cost_manager_selected_job_id
        if not job_id:
            messagebox.showwarning("تنبيه", "يرجى اختيار طلب أولاً.")
            return

        description = self.cost_expense_description_entry.get().strip()
        amount = self.cost_expense_amount_entry.get().strip()
        category = self.cost_expense_category_combo.get().strip() or "أخرى"
        is_included = bool(self.cost_expense_include_switch.get())

        if not description:
            messagebox.showwarning("تنبيه", "يرجى إدخال وصف للمصروف.")
            return
        if not amount:
            messagebox.showwarning("تنبيه", "يرجى إدخال قيمة المصروف.")
            return

        try:
            amount_float = float(amount)
            if amount_float < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("خطأ", "قيمة المصروف يجب أن تكون رقماً موجباً.")
            return

        success, message, _ = self.maintenance_service.add_job_expense(
            job_id=job_id,
            description=description,
            amount=amount_float,
            category=category,
            is_included=is_included
        )

        if success:
            self.load_cost_manager_details(job_id)
            self.refresh_cost_manager_jobs()
            self.clear_cost_expense_form()
            messagebox.showinfo("نجاح", "تمت إضافة المصروف بنجاح.")
        else:
            messagebox.showerror("خطأ", f"فشل في إضافة المصروف: {message}")

    def update_cost_manager_expense(self):
        """تحديث بيانات المصروف المحدد"""
        expense_id = self.cost_selected_expense_id
        if not expense_id:
            messagebox.showwarning("تنبيه", "يرجى اختيار مصروف من القائمة لتحديثه.")
            return

        description = self.cost_expense_description_entry.get().strip()
        amount = self.cost_expense_amount_entry.get().strip()
        category = self.cost_expense_category_combo.get().strip() or "أخرى"
        is_included = bool(self.cost_expense_include_switch.get())

        if not description:
            messagebox.showwarning("تنبيه", "يرجى إدخال وصف للمصروف.")
            return
        if not amount:
            messagebox.showwarning("تنبيه", "يرجى إدخال قيمة المصروف.")
            return

        try:
            amount_float = float(amount)
            if amount_float < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("خطأ", "قيمة المصروف يجب أن تكون رقماً موجباً.")
            return

        success, message = self.maintenance_service.update_job_expense(
            expense_id=expense_id,
            description=description,
            amount=amount_float,
            category=category,
            is_included=is_included
        )

        if success:
            job_id = self.cost_manager_selected_job_id
            if job_id:
                self.load_cost_manager_details(job_id)
                self.refresh_cost_manager_jobs()
            messagebox.showinfo("نجاح", "تم تحديث المصروف بنجاح.")
        else:
            messagebox.showerror("خطأ", f"فشل في تحديث المصروف: {message}")

    def delete_cost_manager_expense(self):
        """حذف المصروف المحدد"""
        expense_id = self.cost_selected_expense_id
        if not expense_id:
            messagebox.showwarning("تنبيه", "يرجى اختيار مصروف من القائمة لحذفه.")
            return

        if not messagebox.askyesno("تأكيد الحذف", "هل أنت متأكد من حذف المصروف المحدد؟"):
            return

        success, message = self.maintenance_service.delete_job_expense(expense_id)
        if success:
            job_id = self.cost_manager_selected_job_id
            if job_id:
                self.load_cost_manager_details(job_id)
                self.refresh_cost_manager_jobs()
            messagebox.showinfo("نجاح", "تم حذف المصروف.")
        else:
            messagebox.showerror("خطأ", f"فشل في حذف المصروف: {message}")

    def toggle_cost_manager_expense_include(self):
        """تغيير حالة التضمين للمصروف المحدد"""
        expense_id = self.cost_selected_expense_id
        if not expense_id:
            messagebox.showwarning("تنبيه", "يرجى اختيار مصروف من القائمة.")
            return

        expense_data = self.cost_expenses_map.get(str(expense_id))
        if not expense_data:
            return

        new_state = not bool(expense_data.get("is_included"))
        success, message = self.maintenance_service.update_job_expense(
            expense_id=expense_id,
            is_included=new_state
        )

        if success:
            job_id = self.cost_manager_selected_job_id
            if job_id:
                self.load_cost_manager_details(job_id)
                self.refresh_cost_manager_jobs()
            messagebox.showinfo("نجاح", "تم تحديث حالة التضمين للمصروف.")
        else:
            messagebox.showerror("خطأ", f"فشل في تحديث حالة التضمين: {message}")

    def on_cost_expense_selected(self):
        """عند تحديد مصروف من الجدول"""
        if not getattr(self, 'cost_expenses_tree', None):
            return
        selection = self.cost_expenses_tree.selection()
        if not selection:
            self.cost_selected_expense_id = None
            self.clear_cost_expense_form()
            return

        expense_id = selection[0]
        expense_data = self.cost_expenses_map.get(expense_id)
        if not expense_data:
            return

        self.cost_selected_expense_id = int(expense_id)
        self.cost_expense_description_entry.delete(0, tk.END)
        self.cost_expense_description_entry.insert(0, expense_data.get("description") or "")

        self.cost_expense_amount_entry.delete(0, tk.END)
        self.cost_expense_amount_entry.insert(0, f"{expense_data.get('amount', 0.0):.2f}")

        category = expense_data.get("category") or "أخرى"
        if category not in ["قطع غيار", "هندسة", "شحن", "ضمان", "أخرى"]:
            category = "أخرى"
        self.cost_expense_category_combo.set(category)

        if expense_data.get("is_included"):
            self.cost_expense_include_switch.select()
        else:
            self.cost_expense_include_switch.deselect()

    def clear_cost_expense_form(self):
        """إعادة ضبط نموذج المصروف"""
        if not getattr(self, 'cost_expense_description_entry', None):
            return
        self.cost_expense_description_entry.delete(0, tk.END)
        self.cost_expense_amount_entry.delete(0, tk.END)
        if getattr(self, 'cost_expense_category_combo', None):
            self.cost_expense_category_combo.set("قطع غيار")
        if getattr(self, 'cost_expense_include_switch', None):
            self.cost_expense_include_switch.select()

    def show_profit_report_window(self):
        """عرض نافذة تقارير الأرباح المحمية"""
        messagebox.showinfo("تنبيه", "ميزة تقارير الأرباح غير متاحة حالياً.")
        return
        if not hasattr(self, 'maintenance_service'):
            messagebox.showerror("خطأ", "خدمة الصيانة غير متاحة.")
            return

        stored_pin = self.maintenance_service.get_system_setting("profit_report_pin", "1234")
        if stored_pin:
            entered_pin = simpledialog.askstring("رمز الدخول", "الرجاء إدخال الرمز السري للوصول إلى تقرير الأرباح:", parent=self, show="*")
            if entered_pin is None:
                return
            if entered_pin != stored_pin:
                messagebox.showerror("رفض الوصول", "الرمز المدخل غير صحيح.")
                return

        if self.profit_report_window and self.profit_report_window.winfo_exists():
            self.profit_report_window.focus()
            return

        self.profit_report_window = ctk.CTkToplevel(self)
        window = self.profit_report_window
        window.title("📊 تقرير الأرباح اليومي - ADR ELECTRONICS")
        window.geometry("1000x700")
        window.resizable(True, True)
        window.grab_set()
        window.focus_force()
        window.protocol("WM_DELETE_WINDOW", self.close_profit_report_window)

        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(window)

        controls_frame = ctk.CTkFrame(window, fg_color="transparent")
        controls_frame.pack(fill=tk.X, padx=20, pady=(20, 10))

        today = datetime.now().strftime("%Y-%m-%d")
        self.profit_start_var = tk.StringVar(value=today)
        self.profit_end_var = tk.StringVar(value=today)

        ctk.CTkLabel(controls_frame, text="بداية الفترة:", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkEntry(controls_frame, textvariable=self.profit_start_var, width=120).pack(side=tk.LEFT, padx=(0, 10))

        ctk.CTkLabel(controls_frame, text="نهاية الفترة:", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkEntry(controls_frame, textvariable=self.profit_end_var, width=120).pack(side=tk.LEFT, padx=(0, 15))

        ctk.CTkButton(
            controls_frame,
            text="عرض التقرير",
            fg_color="#1976D2",
            hover_color="#0D47A1",
            command=self.refresh_profit_report
        ).pack(side=tk.LEFT, padx=(0, 10))

        quick_buttons = ctk.CTkFrame(controls_frame, fg_color="transparent")
        quick_buttons.pack(side=tk.RIGHT)

        ctk.CTkButton(quick_buttons, text="اليوم", width=70, command=lambda: self.set_profit_period("today")).pack(side=tk.LEFT, padx=3)
        ctk.CTkButton(quick_buttons, text="هذا الأسبوع", width=110, command=lambda: self.set_profit_period("week")).pack(side=tk.LEFT, padx=3)
        ctk.CTkButton(quick_buttons, text="هذا الشهر", width=110, command=lambda: self.set_profit_period("month")).pack(side=tk.LEFT, padx=3)
        ctk.CTkButton(quick_buttons, text="هذه السنة", width=110, command=lambda: self.set_profit_period("year")).pack(side=tk.LEFT, padx=3)

        summary_frame = ctk.CTkFrame(window, corner_radius=10, fg_color="#F5F5F5")
        summary_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

        self.profit_summary_labels = {
            "jobs": ctk.CTkLabel(summary_frame, text="عدد الطلبات: --", font=("Arial", 13, "bold")),
            "revenue": ctk.CTkLabel(summary_frame, text="الإيراد الكلي: --", font=("Arial", 13, "bold"), text_color="#1B5E20"),
            "expenses": ctk.CTkLabel(summary_frame, text="إجمالي المصاريف: --", font=("Arial", 13, "bold"), text_color="#C62828"),
            "net": ctk.CTkLabel(summary_frame, text="صافي الربح: --", font=("Arial", 13, "bold"), text_color="#1565C0"),
            "average": ctk.CTkLabel(summary_frame, text="متوسط الربح لكل طلب: --", font=("Arial", 12))
        }

        summary_row = ctk.CTkFrame(summary_frame, fg_color="transparent")
        summary_row.pack(fill=tk.X, padx=15, pady=10)
        self.profit_summary_labels["jobs"].pack(in_=summary_row, side=tk.LEFT, padx=5)
        self.profit_summary_labels["revenue"].pack(in_=summary_row, side=tk.LEFT, padx=5)
        self.profit_summary_labels["expenses"].pack(in_=summary_row, side=tk.LEFT, padx=5)
        self.profit_summary_labels["net"].pack(in_=summary_row, side=tk.LEFT, padx=5)
        self.profit_summary_labels["average"].pack(in_=summary_row, side=tk.RIGHT, padx=5)

        self.profit_result_label = ctk.CTkLabel(
            summary_frame,
            text="النتيجة الصافية: --",
            font=("Arial", 16, "bold"),
            text_color="#2E7D32"
        )
        self.profit_result_label.pack(pady=(0, 10))

        # تقسيم المحتوى إلى جدول الطلبات وجدول الفئات
        content_frame = ctk.CTkFrame(window, fg_color="transparent")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        jobs_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        jobs_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ctk.CTkLabel(jobs_frame, text="تفاصيل الطلبات", font=("Arial", 14, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 5))

        self.profit_jobs_tree = ttk.Treeview(
            jobs_frame,
            columns=("tracking", "customer", "date", "revenue", "expenses", "net"),
            show="headings"
        )
        self.profit_jobs_tree.heading("tracking", text="رقم التتبع")
        self.profit_jobs_tree.heading("customer", text="العميل")
        self.profit_jobs_tree.heading("date", text="تاريخ التسليم")
        self.profit_jobs_tree.heading("revenue", text="الإيراد ($)")
        self.profit_jobs_tree.heading("expenses", text="المصاريف ($)")
        self.profit_jobs_tree.heading("net", text="الصافي ($)")

        self.profit_jobs_tree.column("tracking", width=110, anchor=tk.CENTER)
        self.profit_jobs_tree.column("customer", width=150)
        self.profit_jobs_tree.column("date", width=130, anchor=tk.CENTER)
        self.profit_jobs_tree.column("revenue", width=110, anchor=tk.E)
        self.profit_jobs_tree.column("expenses", width=110, anchor=tk.E)
        self.profit_jobs_tree.column("net", width=110, anchor=tk.E)

        jobs_scroll = ttk.Scrollbar(jobs_frame, orient=tk.VERTICAL, command=self.profit_jobs_tree.yview)
        self.profit_jobs_tree.configure(yscroll=jobs_scroll.set)
        self.profit_jobs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=(0, 15))
        jobs_scroll.pack(side=tk.LEFT, fill=tk.Y, pady=(0, 15))

        categories_frame = ctk.CTkFrame(content_frame, corner_radius=10)
        categories_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(10, 0))

        ctk.CTkLabel(categories_frame, text="المصاريف حسب الفئة", font=("Arial", 14, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 5))

        self.profit_categories_tree = ttk.Treeview(
            categories_frame,
            columns=("category", "total"),
            show="headings",
            height=12
        )
        self.profit_categories_tree.heading("category", text="الفئة")
        self.profit_categories_tree.heading("total", text="الإجمالي ($)")
        self.profit_categories_tree.column("category", width=160)
        self.profit_categories_tree.column("total", width=120, anchor=tk.E)
        self.profit_categories_tree.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        export_frame = ctk.CTkFrame(window, fg_color="transparent")
        export_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        ctk.CTkButton(
            export_frame,
            text="💾 تصدير التقرير إلى CSV",
            fg_color="#00897B",
            hover_color="#00695C",
            command=self.export_profit_report
        ).pack(side=tk.LEFT)

        self.current_profit_summary = None
        self.refresh_profit_report()

    def close_profit_report_window(self):
        """إغلاق نافذة تقرير الأرباح"""
        if self.profit_report_window and self.profit_report_window.winfo_exists():
            self.profit_report_window.destroy()
        self.profit_report_window = None
        self.current_profit_summary = None
        self.profit_jobs_tree = None
        self.profit_categories_tree = None
        self.profit_start_var = None
        self.profit_end_var = None
        self.profit_summary_labels = {}

    def set_profit_period(self, period: str):
        """تعيين نطاق التاريخ وفقاً للاختصار المحدد"""
        today = datetime.now()
        if period == "today":
            start = end = today.date()
        elif period == "week":
            start = (today - timedelta(days=today.weekday())).date()
            end = (start + timedelta(days=6))
        elif period == "month":
            start = today.replace(day=1).date()
            # الحصول على آخر يوم في الشهر
            next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            end = (next_month - timedelta(days=1)).date()
        elif period == "year":
            start = today.replace(month=1, day=1).date()
            end = today.replace(month=12, day=31).date()
        else:
            return

        self.profit_start_var.set(start.strftime("%Y-%m-%d"))
        self.profit_end_var.set(end.strftime("%Y-%m-%d"))
        self.refresh_profit_report()

    def refresh_profit_report(self):
        """تحديث تقرير الأرباح للفترة المحددة"""
        if not hasattr(self, 'maintenance_service'):
            return

        try:
            start_str = self.profit_start_var.get().strip()
            end_str = self.profit_end_var.get().strip()
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            if end_date < start_date:
                raise ValueError("end_before_start")

            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
        except ValueError:
            messagebox.showerror("خطأ", "يرجى إدخال تواريخ صحيحة بالصيغة YYYY-MM-DD.")
            return

        success, message, summary = self.maintenance_service.get_profit_summary(start_dt, end_dt)
        if not success:
            messagebox.showerror("خطأ", f"فشل في إنشاء التقرير: {message}")
            return

        self.current_profit_summary = summary

        jobs_count = summary.get("jobs_count", 0)
        total_revenue = summary.get("total_revenue", 0.0)
        total_expenses = summary.get("total_expenses", 0.0)
        net_profit = summary.get("net_profit", 0.0)
        avg_profit = summary.get("average_profit", 0.0)

        self.profit_summary_labels["jobs"].configure(text=f"عدد الطلبات: {self.format_number_english(jobs_count)}")
        self.profit_summary_labels["revenue"].configure(text=f"الإيراد الكلي: ${total_revenue:.2f}")
        self.profit_summary_labels["expenses"].configure(text=f"إجمالي المصاريف: ${total_expenses:.2f}")
        self.profit_summary_labels["net"].configure(text=f"صافي الربح: ${net_profit:.2f}")
        self.profit_summary_labels["average"].configure(text=f"متوسط الربح لكل طلب: ${avg_profit:.2f}")
        if getattr(self, 'profit_result_label', None):
            self.profit_result_label.configure(text=f"النتيجة الصافية: {net_profit:.2f} $")

        if getattr(self, 'profit_jobs_tree', None):
            self.profit_jobs_tree.delete(*self.profit_jobs_tree.get_children())
            for job in summary.get("jobs", []):
                delivered_at = job.get("delivered_at")
                date_str = delivered_at.strftime("%Y-%m-%d") if delivered_at else "-"
                self.profit_jobs_tree.insert(
                    "",
                    tk.END,
                    values=(
                        job.get("tracking_code", "-"),
                        job.get("customer", "غير محدد"),
                        date_str,
                        f"{job.get('revenue', 0.0):.2f}",
                        f"{job.get('expenses', 0.0):.2f}",
                        f"{job.get('net', 0.0):.2f}"
                    )
                )

        if getattr(self, 'profit_categories_tree', None):
            self.profit_categories_tree.delete(*self.profit_categories_tree.get_children())
            for category in summary.get("categories", []):
                self.profit_categories_tree.insert(
                    "",
                    tk.END,
                    values=(
                        category.get("category", "غير محدد"),
                        f"{category.get('total', 0.0):.2f}"
                    )
                )

    def export_profit_report(self):
        """تصدير تقرير الأرباح الحالي إلى ملف CSV"""
        if not self.current_profit_summary:
            messagebox.showwarning("تنبيه", "لا يوجد تقرير متاح للتصدير.")
            return

        default_filename = f"profit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        initial_dir = REPORTS_FOLDER if os.path.isdir(REPORTS_FOLDER) else os.getcwd()
        file_path = filedialog.asksaveasfilename(
            title="حفظ تقرير الأرباح",
            initialdir=initial_dir,
            initialfile=default_filename,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")]
        )
        if not file_path:
            return

        summary = self.current_profit_summary
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["تقرير الأرباح", datetime.now().strftime("%Y-%m-%d %H:%M")])
                writer.writerow([])
                writer.writerow(["الفترة", summary["period"]["start"].strftime("%Y-%m-%d"), summary["period"]["end"].strftime("%Y-%m-%d")])
                writer.writerow(["عدد الطلبات", summary.get("jobs_count", 0)])
                writer.writerow(["الإيراد الكلي ($)", f"{summary.get('total_revenue', 0.0):.2f}"])
                writer.writerow(["إجمالي المصاريف ($)", f"{summary.get('total_expenses', 0.0):.2f}"])
                writer.writerow(["صافي الربح ($)", f"{summary.get('net_profit', 0.0):.2f}"])
                writer.writerow(["متوسط الربح لكل طلب ($)", f"{summary.get('average_profit', 0.0):.2f}"])
                writer.writerow([])

                writer.writerow(["تفاصيل الطلبات"])
                writer.writerow(["رقم التتبع", "العميل", "تاريخ التسليم", "الإيراد ($)", "المصاريف ($)", "الصافي ($)"])
                for job in summary.get("jobs", []):
                    delivered_at = job.get("delivered_at")
                    writer.writerow([
                        job.get("tracking_code", "-"),
                        job.get("customer", "غير محدد"),
                        delivered_at.strftime("%Y-%m-%d") if delivered_at else "-",
                        f"{job.get('revenue', 0.0):.2f}",
                        f"{job.get('expenses', 0.0):.2f}",
                        f"{job.get('net', 0.0):.2f}"
                    ])

                writer.writerow([])
                writer.writerow(["المصاريف حسب الفئة"])
                writer.writerow(["الفئة", "الإجمالي ($)"])
                for category in summary.get("categories", []):
                    writer.writerow([
                        category.get("category", "غير محدد"),
                        f"{category.get('total', 0.0):.2f}"
                    ])

            messagebox.showinfo("نجاح", f"تم حفظ التقرير في:\n{file_path}")
        except Exception as exc:
            messagebox.showerror("خطأ", f"فشل في حفظ التقرير: {str(exc)}")

    def generate_whatsapp_notification(self, job_id, status, price="", price_currency=None):
        """إنشاء رابط إشعار WhatsApp مع الرسائل المخصصة"""
        try:
            # الحصول على بيانات الطلب من قاعدة البيانات
            db = next(get_db())
            job_obj = db.query(MaintenanceJob).filter_by(id=job_id).first()
            
            if not job_obj:
                return None
            
            # التحقق من تفعيل الإرسال التلقائي
            maintenance_service = MaintenanceService(db)
            auto_send_enabled = maintenance_service.get_system_setting("whatsapp_auto_send", "true")
            if auto_send_enabled.lower() != "true":
                return None
            
            # الحصول على الرسالة المخصصة حسب الحالة
            if status == "received":
                # إلغاء رسالة تم الاستلام بناءً على طلب المستخدم
                return None
            elif status == "repaired":
                message_template = maintenance_service.get_system_setting(
                    "whatsapp_repaired_message",
                    WHATSAPP_REPAIRED_MESSAGE
                )
            elif status == "delivered":
                message_template = maintenance_service.get_system_setting(
                    "whatsapp_delivered_message",
                    WHATSAPP_DELIVERED_MESSAGE
                )
            else:
                # استخدام الرسالة الافتراضية للحالات الأخرى
                message_template = maintenance_service.get_system_setting(
                    "whatsapp_message_template",
                    config.DEFAULT_WHATSAPP_TEMPLATE
                )
            
            def parse_amount(value: str):
                """تنظيف وتحويل النص إلى رقم"""
                if not value:
                    return None
                cleaned = value.replace(" ", "").replace(",", "").replace("ل.ل", "").replace("$", "")
                try:
                    return float(cleaned)
                except ValueError:
                    return None

            def format_amount(amount: float, currency_code: str) -> str:
                """تنسيق المبلغ بناءً على العملة"""
                currency_code = (currency_code or config.DEFAULT_CURRENCY).upper()
                symbol = config.CURRENCY_SYMBOL.get(currency_code, currency_code)
                if currency_code == "LBP":
                    return f"{amount:,.0f} ل.ل"
                if currency_code == "USD":
                    return f"${amount:.2f}"
                return f"{amount:.2f} {symbol}"

            # إعداد معلومات السعر وفق العملة المحفوظة
            price_info = ""
            if price and status == 'repaired':
                detected_currency = (
                    price_currency
                    or job_obj.final_cost_currency
                    or job_obj.estimated_cost_currency
                    or config.DEFAULT_CURRENCY
                ).upper()
                parsed_amount = parse_amount(price)
                if parsed_amount is not None:
                    price_info = f"السعر: {format_amount(parsed_amount, detected_currency)}"
                else:
                    if detected_currency == "LBP":
                        price_info = f"السعر: {price} ل.ل"
                    elif detected_currency == "USD":
                        price_info = f"السعر: ${price}"
                    else:
                        symbol = config.CURRENCY_SYMBOL.get(detected_currency, detected_currency)
                        price_info = f"السعر: {price} {symbol}"
            
            # ترجمة الحالة
            status_translations = {
                'received': 'تم الاستلام',
                'repaired': 'تمت الصيانة',
                'delivered': 'تم التسليم'
            }
            arabic_status = status_translations.get(status, status)
            
            # تنظيف القالب من حقول غير مدعومة لمنع أخطاء الفورمات
            message_template = message_template.replace("{customer_name}", "").replace("{device_model}", "")

            # ملء القالب بالبيانات (بدون اسم العميل والموديل)
            message = message_template.format(
                tracking_code=job_obj.tracking_code,
                device_type=job_obj.device_type or "غير محدد",
                serial_number=job_obj.serial_number or "غير محدد",
                status=arabic_status,
                price_info=price_info,
                date=datetime.now().strftime('%Y-%m-%d %H:%M')
            )
            
            # إنشاء رابط WhatsApp
            phone = job_obj.customer.phone.replace('+', '').replace(' ', '').replace('-', '')
            if not phone.startswith('961'):
                phone = '961' + phone.lstrip('0')
            
            whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
            return whatsapp_url
            
        except Exception as e:
            print(f"خطأ في إنشاء رابط WhatsApp: {e}")
            return None
        finally:
            db.close()