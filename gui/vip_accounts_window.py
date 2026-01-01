"""
واجهة إدارة حسابات العملاء المميزين
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from database.connection import get_db
from database.models import VIPCustomer, Customer, MaintenanceJob, AccountTransaction, WhatsAppSchedule
from services.maintenance_service import MaintenanceService


class VIPAccountsWindow(ctk.CTkToplevel):
    def setup_enter_navigation(self, parent_widget):
        """إعداد التنقل بالـ Enter لجميع حقول الإدخال في النافذة"""
        def find_all_inputs(widget, inputs_list):
            """البحث عن جميع حقول الإدخال في النافذة"""
            try:
                if isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox)):
                    inputs_list.append(widget)
                elif isinstance(widget, ctk.CTkComboBox):
                    inputs_list.append(widget)
                for child in widget.winfo_children():
                    find_all_inputs(child, inputs_list)
            except:
                pass
        
        inputs = []
        find_all_inputs(parent_widget, inputs)
        
        for i, input_widget in enumerate(inputs):
            def make_navigate_handler(current_idx):
                def navigate_on_enter(event):
                    next_idx = (current_idx + 1) % len(inputs)
                    next_widget = inputs[next_idx]
                    if isinstance(next_widget, ctk.CTkTextbox):
                        next_widget.focus()
                        try:
                            next_widget.mark_set(tk.INSERT, "1.0")
                        except:
                            pass
                    else:
                        next_widget.focus()
                    try:
                        parent = next_widget.master
                        while parent:
                            if isinstance(parent, ctk.CTkScrollableFrame):
                                next_widget.update_idletasks()
                                widget_y = next_widget.winfo_y()
                                parent_height = parent.winfo_height()
                                if widget_y > parent_height:
                                    relative_y = widget_y / parent.winfo_reqheight() if parent.winfo_reqheight() > 0 else 0
                                    parent._parent_canvas.yview_moveto(max(0, min(1, relative_y - 0.2)))
                                break
                            try:
                                parent = parent.master
                            except:
                                break
                    except:
                        pass
                    return "break"
                return navigate_on_enter
            
            input_widget.bind('<Return>', make_navigate_handler(i))
            input_widget.bind('<KP_Enter>', make_navigate_handler(i))
        
        def find_all_trees(widget, trees_list):
            try:
                if isinstance(widget, ttk.Treeview):
                    trees_list.append(widget)
                for child in widget.winfo_children():
                    find_all_trees(child, trees_list)
            except:
                pass
        
        trees = []
        find_all_trees(parent_widget, trees)
        
        for tree in trees:
            def make_tree_navigate_handler(tree_widget):
                def navigate_tree_on_enter(event):
                    selection = tree_widget.selection()
                    if selection:
                        current_item = selection[0]
                        next_item = tree_widget.next(current_item)
                        if not next_item:
                            children = tree_widget.get_children()
                            if children:
                                next_item = children[0]
                        if next_item:
                            tree_widget.selection_set(next_item)
                            tree_widget.focus(next_item)
                            tree_widget.see(next_item)
                    else:
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
    
    """نافذة إدارة حسابات العملاء المميزين"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.maintenance_service = MaintenanceService(next(get_db()))
        
        self.title("إدارة حسابات العملاء المميزين")
        self.geometry("1200x800")
        self.grab_set()
        
        self.setup_ui()
        self.load_vip_customers()
        
        # إعداد التنقل بالـ Enter
        self.setup_enter_navigation(self)
    
    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        # شريط الأدوات
        toolbar = ctk.CTkFrame(self, height=50)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkButton(
            toolbar, 
            text="➕ إضافة عميل مميز", 
            command=self.add_vip_customer,
            fg_color="#28a745",
            hover_color="#218838"
        ).pack(side=tk.RIGHT, padx=5)
        
        def refresh_data():
            """تحديث البيانات"""
            if hasattr(self, 'current_vip_id'):
                print("🔄 تحديث البيانات...")
                self.load_customer_details(self.current_vip_id)
                messagebox.showinfo("نجاح", "تم تحديث البيانات")
            else:
                self.load_vip_customers()
        
        ctk.CTkButton(
            toolbar, 
            text="🔄 تحديث", 
            command=refresh_data,
            fg_color="#2196F3",
            hover_color="#1976D2"
        ).pack(side=tk.RIGHT, padx=5)
        
        ctk.CTkButton(
            toolbar, 
            text="🔍 بحث", 
            command=self.search_customers
        ).pack(side=tk.LEFT, padx=5)
        
        search_entry = ctk.CTkEntry(toolbar, width=200, placeholder_text="ابحث عن عميل...")
        search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry = search_entry
        search_entry.bind('<Return>', lambda e: self.search_customers())
        
        # المحتوى الرئيسي
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # قائمة العملاء المميزين
        list_frame = ctk.CTkFrame(main_frame, width=300)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        list_frame.pack_propagate(False)
        
        ctk.CTkLabel(list_frame, text="العملاء المميزين", font=("Arial", 14, "bold")).pack(pady=10)
        
        # قائمة العملاء
        self.customers_tree = ttk.Treeview(list_frame, columns=("name",), show="tree headings")
        self.customers_tree.heading("#0", text="")
        self.customers_tree.heading("name", text="الاسم")
        self.customers_tree.column("#0", width=0, stretch=tk.NO)
        self.customers_tree.column("name", width=280)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.customers_tree.yview)
        self.customers_tree.configure(yscroll=scrollbar.set)
        
        self.customers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.customers_tree.bind("<<TreeviewSelect>>", self.on_customer_select)
        
        # تفاصيل الحساب
        details_frame = ctk.CTkFrame(main_frame)
        details_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # علامات التبويب
        self.tabview = ctk.CTkTabview(details_frame)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.tabview.add("المعلومات العامة")
        self.tabview.add("الطلبات والأجهزة")
        self.tabview.add("إعدادات واتساب")
        self.tabview.add("كشف الحساب")
        
        self.setup_general_tab()
        self.setup_orders_tab()
        self.setup_whatsapp_tab()
        self.setup_statement_tab()
    
    def setup_general_tab(self):
        """إعداد تبويب المعلومات العامة"""
        tab = self.tabview.tab("المعلومات العامة")
        
        scrollable = ctk.CTkScrollableFrame(tab)
        scrollable.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # معلومات العميل - مبسطة
        info_frame = ctk.CTkFrame(scrollable, fg_color="#e3f2fd", corner_radius=10)
        info_frame.pack(fill=tk.X, pady=20, padx=20)
        
        ctk.CTkLabel(
            info_frame, 
            text="معلومات العميل", 
            font=("Arial", 16, "bold"),
            text_color="#1976d2"
        ).pack(pady=(20, 15))
        
        # اسم العميل
        name_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        name_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkLabel(
            name_frame, 
            text="الاسم:", 
            font=("Arial", 14, "bold"),
            width=100
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.name_label = ctk.CTkLabel(
            name_frame, 
            text="-", 
            font=("Arial", 14),
            anchor="w"
        )
        self.name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # رقم الهاتف
        phone_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        phone_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ctk.CTkLabel(
            phone_frame, 
            text="الهاتف:", 
            font=("Arial", 14, "bold"),
            width=100
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.phone_label = ctk.CTkLabel(
            phone_frame, 
            text="-", 
            font=("Arial", 14),
            anchor="w"
        )
        self.phone_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # أزرار
        btn_frame = ctk.CTkFrame(scrollable, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=20, padx=20)
        
        ctk.CTkButton(
            btn_frame, 
            text="🗑️ حذف العميل", 
            command=self.delete_vip_customer,
            fg_color="#dc3545",
            hover_color="#c82333",
            width=150,
            height=40,
            font=("Arial", 12, "bold")
        ).pack(side=tk.LEFT, padx=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="🔄 تحديث", 
            command=lambda: self.load_customer_details(self.current_vip_id) if hasattr(self, 'current_vip_id') and self.current_vip_id else None,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=150,
            height=40,
            font=("Arial", 12, "bold")
        ).pack(side=tk.RIGHT, padx=10)
        
        # إخفاء زر حفظ التغييرات لأنه لم يعد هناك إعدادات للحفظ
        # تم تبسيط الواجهة لعرض اسم العميل ورقم الهاتف فقط
    
    def setup_orders_tab(self):
        """إعداد تبويب الطلبات والأجهزة"""
        tab = self.tabview.tab("الطلبات والأجهزة")
        
        # إطار الأزرار
        btn_frame = ctk.CTkFrame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ctk.CTkButton(
            btn_frame,
            text="➕ إضافة دفعة",
            command=self.add_free_payment,
            fg_color="#28a745",
            hover_color="#218838"
        ).pack(side=tk.RIGHT, padx=5)
        
        # إطار الجدول
        table_frame = ctk.CTkFrame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # جدول الطلبات
        columns = ("tracking_code", "device_type", "status", "cost", "payment_status", "date")
        self.orders_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        self.orders_tree.heading("tracking_code", text="رقم التتبع")
        self.orders_tree.heading("device_type", text="نوع الجهاز")
        self.orders_tree.heading("status", text="الحالة")
        self.orders_tree.heading("cost", text="التكلفة")
        self.orders_tree.heading("payment_status", text="حالة الدفع")
        self.orders_tree.heading("date", text="التاريخ")
        
        self.orders_tree.column("tracking_code", width=120)
        self.orders_tree.column("device_type", width=150)
        self.orders_tree.column("status", width=100)
        self.orders_tree.column("cost", width=100)
        self.orders_tree.column("payment_status", width=120)
        self.orders_tree.column("date", width=120)
        
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.orders_tree.yview)
        self.orders_tree.configure(yscroll=scrollbar.set)
        
        self.orders_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # إطار الملخص
        summary_frame = ctk.CTkFrame(tab)
        summary_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.total_cost_label = ctk.CTkLabel(
            summary_frame,
            text="إجمالي الكلفة: 0.00 $",
            font=("Arial", 14, "bold"),
            text_color="#2196F3"
        )
        self.total_cost_label.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def setup_whatsapp_tab(self):
        """إعداد تبويب إعدادات واتساب"""
        tab = self.tabview.tab("إعدادات واتساب")
        
        scrollable = ctk.CTkScrollableFrame(tab)
        scrollable.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(scrollable, text="جدولة الرسائل التلقائية", font=("Arial", 14, "bold")).pack(pady=10)
        
        # قائمة الجداول
        self.schedules_listbox = tk.Listbox(scrollable, height=10)
        self.schedules_listbox.pack(fill=tk.X, padx=10, pady=5)
        
        btn_frame = ctk.CTkFrame(scrollable)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="➕ إضافة جدول", 
            command=self.add_whatsapp_schedule,
            fg_color="#17a2b8",
            hover_color="#138496"
        ).pack(side=tk.RIGHT, padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="✏️ تعديل", 
            command=self.edit_whatsapp_schedule
        ).pack(side=tk.RIGHT, padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="🗑️ حذف", 
            command=self.delete_whatsapp_schedule,
            fg_color="#dc3545",
            hover_color="#c82333"
        ).pack(side=tk.RIGHT, padx=5)
        
        # زر إرسال رسالة فورية
        ctk.CTkButton(
            scrollable, 
            text="📱 إرسال رسالة واتساب الآن", 
            command=self.send_whatsapp_now,
            fg_color="#25d366",
            hover_color="#128c7e",
            height=40,
            font=("Arial", 12, "bold")
        ).pack(fill=tk.X, padx=10, pady=10)
    
    def setup_statement_tab(self):
        """إعداد تبويب كشف الحساب"""
        tab = self.tabview.tab("كشف الحساب")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # شريط الأدوات العلوي
        toolbar_frame = ctk.CTkFrame(tab)
        toolbar_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        toolbar_frame.grid_columnconfigure(0, weight=1)
        
        # الأزرار
        buttons_frame = ctk.CTkFrame(toolbar_frame, fg_color="transparent")
        buttons_frame.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        
        ctk.CTkButton(
            buttons_frame, 
            text="➕ إضافة دفعة", 
            command=self.add_free_payment,
            fg_color="#28a745",
            hover_color="#218838",
            width=120
        ).pack(side=tk.RIGHT, padx=3)
        
        ctk.CTkButton(
            buttons_frame, 
            text="📱 إرسال واتساب", 
            command=self.send_statement_whatsapp,
            fg_color="#25d366",
            hover_color="#128c7e",
            width=120
        ).pack(side=tk.RIGHT, padx=3)
        
        ctk.CTkButton(
            buttons_frame, 
            text="📄 طباعة", 
            command=self.print_statement,
            width=100
        ).pack(side=tk.RIGHT, padx=3)
        
        # المحتوى الرئيسي
        content_frame = ctk.CTkFrame(tab)
        content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)
        
        # ملخص الرصيد
        summary_frame = ctk.CTkFrame(content_frame, fg_color="#e3f2fd", corner_radius=10)
        summary_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        summary_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # تسميات الملخص
        self.balance_labels = {}
        
        # إجمالي الديون
        debt_frame = ctk.CTkFrame(summary_frame, fg_color="transparent")
        debt_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ctk.CTkLabel(debt_frame, text="إجمالي الديون", font=("Arial", 12, "bold"), text_color="#d32f2f").pack()
        self.balance_labels['total_debt'] = ctk.CTkLabel(debt_frame, text="0.00 $", font=("Arial", 18, "bold"), text_color="#d32f2f")
        self.balance_labels['total_debt'].pack()
        
        # إجمالي المدفوعات
        payment_frame = ctk.CTkFrame(summary_frame, fg_color="transparent")
        payment_frame.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkLabel(payment_frame, text="إجمالي المدفوعات", font=("Arial", 12, "bold"), text_color="#388e3c").pack()
        self.balance_labels['total_payment'] = ctk.CTkLabel(payment_frame, text="0.00 $", font=("Arial", 18, "bold"), text_color="#388e3c")
        self.balance_labels['total_payment'].pack()
        
        # الرصيد الحالي
        balance_frame = ctk.CTkFrame(summary_frame, fg_color="transparent")
        balance_frame.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        ctk.CTkLabel(balance_frame, text="الرصيد الحالي", font=("Arial", 12, "bold"), text_color="#1976d2").pack()
        self.balance_labels['balance'] = ctk.CTkLabel(balance_frame, text="0.00 $", font=("Arial", 20, "bold"), text_color="#1976d2")
        self.balance_labels['balance'].pack()
        
        # حد الائتمان
        credit_frame = ctk.CTkFrame(summary_frame, fg_color="transparent")
        credit_frame.grid(row=0, column=3, padx=10, pady=10, sticky="ew")
        ctk.CTkLabel(credit_frame, text="حد الائتمان", font=("Arial", 12, "bold"), text_color="#7b1fa2").pack()
        self.balance_labels['credit_limit'] = ctk.CTkLabel(credit_frame, text="0.00 $", font=("Arial", 16, "bold"), text_color="#7b1fa2")
        self.balance_labels['credit_limit'].pack()
        
        # تبويبات للدفعات والديون
        statement_tabs = ctk.CTkTabview(content_frame)
        statement_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # تبويب الدفعات
        payments_tab = statement_tabs.add("💵 الدفعات")
        payments_tab.grid_columnconfigure(0, weight=1)
        payments_tab.grid_rowconfigure(0, weight=1)
        
        # جدول الدفعات
        payments_frame = ctk.CTkFrame(payments_tab)
        payments_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        payments_frame.grid_columnconfigure(0, weight=1)
        payments_frame.grid_rowconfigure(0, weight=1)
        
        payments_columns = ("date", "amount", "method", "description")
        self.payments_tree = ttk.Treeview(payments_frame, columns=payments_columns, show="headings", height=10)
        self.payments_tree.heading("date", text="التاريخ")
        self.payments_tree.heading("amount", text="المبلغ")
        self.payments_tree.heading("method", text="طريقة الدفع")
        self.payments_tree.heading("description", text="الوصف")
        
        self.payments_tree.column("date", width=120, anchor=tk.CENTER)
        self.payments_tree.column("amount", width=100, anchor=tk.CENTER)
        self.payments_tree.column("method", width=100, anchor=tk.CENTER)
        self.payments_tree.column("description", width=300, anchor=tk.W)
        
        payments_scrollbar = ttk.Scrollbar(payments_frame, orient=tk.VERTICAL, command=self.payments_tree.yview)
        self.payments_tree.configure(yscroll=payments_scrollbar.set)
        
        self.payments_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        payments_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # تبويب الديون
        debts_tab = statement_tabs.add("📋 الديون")
        debts_tab.grid_columnconfigure(0, weight=1)
        debts_tab.grid_rowconfigure(1, weight=1)
        
        # شريط أدوات الديون
        debts_toolbar = ctk.CTkFrame(debts_tab, fg_color="transparent")
        debts_toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkButton(
            debts_toolbar,
            text="➕ إضافة دين من طلب مسلم",
            command=self.add_debt_from_delivered_job,
            fg_color="#f57c00",
            hover_color="#e65100",
            width=180
        ).pack(side=tk.RIGHT, padx=3)
        
        # جدول الديون
        debts_frame = ctk.CTkFrame(debts_tab)
        debts_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        debts_frame.grid_columnconfigure(0, weight=1)
        debts_frame.grid_rowconfigure(0, weight=1)
        
        debts_columns = ("date", "tracking_code", "device_type", "amount", "description", "status")
        self.debts_tree = ttk.Treeview(debts_frame, columns=debts_columns, show="headings", height=10)
        self.debts_tree.heading("date", text="التاريخ")
        self.debts_tree.heading("tracking_code", text="رقم التتبع")
        self.debts_tree.heading("device_type", text="نوع الجهاز")
        self.debts_tree.heading("amount", text="المبلغ")
        self.debts_tree.heading("description", text="الوصف")
        self.debts_tree.heading("status", text="حالة الطلب")
        
        self.debts_tree.column("date", width=120, anchor=tk.CENTER)
        self.debts_tree.column("tracking_code", width=100, anchor=tk.CENTER)
        self.debts_tree.column("device_type", width=120, anchor=tk.CENTER)
        self.debts_tree.column("amount", width=100, anchor=tk.CENTER)
        self.debts_tree.column("description", width=200, anchor=tk.W)
        self.debts_tree.column("status", width=100, anchor=tk.CENTER)
        
        debts_scrollbar = ttk.Scrollbar(debts_frame, orient=tk.VERTICAL, command=self.debts_tree.yview)
        self.debts_tree.configure(yscroll=debts_scrollbar.set)
        
        self.debts_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        debts_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # نص كشف الحساب (للطباعة)
        self.statement_text = ctk.CTkTextbox(tab, wrap=tk.WORD, height=0)
        self.statement_text.grid_remove()  # إخفاء النص
        
        # ربط حدث النقر المزدوج على جدول الديون لإضافة دين يدوياً
        if hasattr(self, 'debts_tree'):
            self.debts_tree.bind("<Double-1>", self.on_debt_double_click)
    
    def load_vip_customers(self):
        """تحميل قائمة العملاء المميزين"""
        try:
            db = next(get_db())
            vip_customers = db.query(VIPCustomer).join(Customer).all()
            
            # مسح القائمة
            for item in self.customers_tree.get_children():
                self.customers_tree.delete(item)
            
            # إضافة العملاء
            for vip in vip_customers:
                self.customers_tree.insert("", tk.END, values=(vip.customer.name,), tags=(vip.id,))
            
            db.close()
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تحميل العملاء المميزين: {str(e)}")
    
    def on_customer_select(self, event):
        """عند اختيار عميل"""
        selection = self.customers_tree.selection()
        if not selection:
            return
        
        item = self.customers_tree.item(selection[0])
        vip_id = item['tags'][0]
        
        # التأكد من أن vip_id رقم صحيح
        try:
            vip_id = int(vip_id)
            print(f"📌 تم اختيار عميل مميز برقم: {vip_id}")
            self.load_customer_details(vip_id)
        except (ValueError, TypeError) as e:
            print(f"❌ خطأ في معرف العميل المميز: {vip_id}, الخطأ: {e}")
            messagebox.showerror("خطأ", f"خطأ في اختيار العميل: {e}")
    
    def load_customer_details(self, vip_id: int):
        """تحميل تفاصيل العميل"""
        try:
            print(f"📋 جارٍ تحميل تفاصيل العميل المميز ID: {vip_id}")
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == vip_id).first()
            
            if not vip:
                print(f"❌ لم يتم العثور على عميل مميز برقم: {vip_id}")
                messagebox.showwarning("تحذير", f"لم يتم العثور على عميل مميز برقم: {vip_id}")
                db.close()
                return
            
            print(f"✅ تم العثور على عميل مميز: {vip.customer.name if vip.customer else 'غير معروف'}")
            
            # تحميل معلومات العميل - مبسطة
            self.name_label.configure(text=vip.customer.name if vip.customer else "غير معروف")
            self.phone_label.configure(text=vip.customer.phone if vip.customer else "-")
            
            # تحميل الطلبات
            self.load_customer_orders(vip.customer_id)
            
            # تحميل جداول واتساب
            self.load_whatsapp_schedules(vip_id)
            
            # تحديث كشف الحساب
            self.update_statement(vip_id)
            
            self.current_vip_id = vip_id
            db.close()
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تحميل التفاصيل: {str(e)}")
    
    def translate_status_to_arabic(self, status):
        """ترجمة حالة الجهاز إلى العربية"""
        status_translations = {
            'received': 'تم الاستلام',
            'not_repaired': 'لم تتم الصيانة',
            'repaired': 'تم الصيانة',
            'delivered': 'تم التسليم'
        }
        # إذا كان status كائن Enum، استخدم .value
        if hasattr(status, 'value'):
            status_value = status.value
        else:
            status_value = str(status)
        return status_translations.get(status_value, status_value)
    
    def load_customer_orders(self, customer_id: int):
        """تحميل طلبات العميل"""
        try:
            # مسح الجدول
            for item in self.orders_tree.get_children():
                self.orders_tree.delete(item)
            
            db = next(get_db())
            # استخدام استعلام محسّن مع حساب الإجمالي في قاعدة البيانات
            from sqlalchemy import func, case
            from sqlalchemy.orm import joinedload
            
            # جلب الطلبات مع حساب الإجمالي في استعلام واحد
            jobs_query = db.query(
                MaintenanceJob,
                func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0).label('cost')
            ).filter(
                MaintenanceJob.customer_id == customer_id
            ).order_by(MaintenanceJob.received_at.desc())
            
            # حساب الإجمالي في قاعدة البيانات (أسرع)
            total_cost_result = db.query(
                func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0))
            ).filter(
                MaintenanceJob.customer_id == customer_id
            ).scalar() or 0
            
            jobs = jobs_query.all()
            
            # إدراج البيانات في الجدول
            for job_result in jobs:
                job = job_result[0] if isinstance(job_result, tuple) else job_result
                cost = job_result[1] if isinstance(job_result, tuple) else (job.final_cost or job.estimated_cost or 0)
                
                # ترجمة الحالة إلى العربية
                job_status = job.status.value if hasattr(job.status, 'value') else str(job.status)
                arabic_status = self.translate_status_to_arabic(job_status)
                
                # تحديد حالة الدفع
                if job.payment_status == "paid":
                    if job.payment_method == "cash":
                        payment_status = "كاش ✅"
                    elif job.payment_method == "wish_money":
                        payment_status = "ويش موني ✅"
                    else:
                        payment_status = "مدفوع ✅"
                else:
                    payment_status = "دين ❌"
                
                self.orders_tree.insert("", tk.END, values=(
                    job.tracking_code,
                    job.device_type,
                    arabic_status,
                    f"{self.format_number_english(cost):.2f} $",
                    payment_status,
                    job.received_at.strftime("%Y-%m-%d") if job.received_at else ""
                ))
            
            # تحديث مجموع الكلفة
            if hasattr(self, 'total_cost_label'):
                self.total_cost_label.configure(text=f"إجمالي الكلفة: {self.format_number_english(total_cost_result):.2f} $")
            
            db.close()
        except Exception as e:
            print(f"خطأ في تحميل الطلبات: {e}")
            import traceback
            print(traceback.format_exc())
    
    def load_whatsapp_schedules(self, vip_id: int):
        """تحميل جداول واتساب"""
        try:
            self.schedules_listbox.delete(0, tk.END)
            
            db = next(get_db())
            schedules = db.query(WhatsAppSchedule).filter(
                WhatsAppSchedule.vip_customer_id == vip_id
            ).all()
            
            for schedule in schedules:
                status = "نشط" if schedule.is_active else "معطل"
                self.schedules_listbox.insert(tk.END, f"{schedule.message_type} - {schedule.send_time} ({status})")
            
            db.close()
        except Exception as e:
            print(f"خطأ في تحميل الجداول: {e}")
    
    def format_number_english(self, number):
        """تحويل رقم إلى سلسلة نصية بالأرقام الإنجليزية (0-9) دائماً"""
        if number is None:
            return "0"
        number_str = str(number)
        arabic_to_english = {
            '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
            '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        }
        result = ''.join(arabic_to_english.get(char, char) for char in number_str)
        return result
    
    def update_statement(self, vip_id: int):
        """تحديث كشف الحساب"""
        try:
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == vip_id).first()
            
            if not vip:
                db.close()
                return
            
            # تحديث حد الائتمان
            if hasattr(self, 'balance_labels') and 'credit_limit' in self.balance_labels:
                credit_limit_formatted = self.format_number_english(f"{float(vip.credit_limit):.2f}")
                self.balance_labels['credit_limit'].configure(text=f"{credit_limit_formatted} $")
            
            # جلب جميع المعاملات مع eager loading للطلبات
            from sqlalchemy.orm import joinedload
            
            transactions = db.query(AccountTransaction)\
                           .options(joinedload(AccountTransaction.maintenance_job))\
                           .filter(AccountTransaction.vip_customer_id == vip_id)\
                           .order_by(AccountTransaction.created_at.desc())\
                           .all()
            
            # حساب الإجماليات في قاعدة البيانات (أسرع)
            from sqlalchemy import func, case
            totals = db.query(
                func.sum(case((AccountTransaction.transaction_type == "debt", AccountTransaction.amount), else_=0)).label('total_debt'),
                func.sum(case((AccountTransaction.transaction_type == "payment", AccountTransaction.amount), else_=0)).label('total_payment')
            ).filter(AccountTransaction.vip_customer_id == vip_id).first()
            
            total_debt = totals.total_debt or 0
            total_payment = totals.total_payment or 0
            
            # مسح الجداول
            if hasattr(self, 'payments_tree'):
                for item in self.payments_tree.get_children():
                    self.payments_tree.delete(item)
            
            if hasattr(self, 'debts_tree'):
                for item in self.debts_tree.get_children():
                    self.debts_tree.delete(item)
            
            # طباعة للتشخيص
            print(f"🔍 [DEBUG] عدد المعاملات: {len(transactions)}")
            print(f"🔍 [DEBUG] إجمالي الديون: {total_debt:.2f} $")
            print(f"🔍 [DEBUG] إجمالي المدفوعات: {total_payment:.2f} $")
            
            # فصل الدفعات والديون (البيانات محملة مسبقاً)
            payment_count = 0
            debt_count = 0
            
            for trans in transactions:
                date_str = trans.created_at.strftime("%Y-%m-%d") if trans.created_at else ""
                
                if trans.transaction_type == "payment":
                    # دفعة
                    payment_count += 1
                    payment_method = "كاش" if trans.payment_method == "cash" else "ويش موني" if trans.payment_method == "wish_money" else "أخرى"
                    
                    if hasattr(self, 'payments_tree'):
                        amount_formatted = self.format_number_english(f"{trans.amount:.2f}")
                        print(f"🔍 [DEBUG] إضافة دفعة: {date_str}, {amount_formatted} $, {payment_method}, {trans.description or 'دفعة'}")
                        self.payments_tree.insert("", tk.END, values=(
                            date_str,
                            f"{amount_formatted} $",
                            payment_method,
                            trans.description or "دفعة"
                        ))
                
                elif trans.transaction_type == "debt":
                    # دين
                    debt_count += 1
                    # الحصول على معلومات الطلب (محمل مسبقاً)
                    tracking_code = "-"
                    device_type = "-"
                    job_status_display = "-"
                    
                    if trans.maintenance_job_id and trans.maintenance_job:
                        job = trans.maintenance_job
                        tracking_code = job.tracking_code
                        device_type = job.device_type
                        job_status_value = job.status.value if hasattr(job.status, 'value') else str(job.status)
                        job_status_arabic = self.translate_status_to_arabic(job_status_value)
                        
                        # عرض حالة الطلب مع إشارة للطلبات المسلمة
                        if job_status_value == "delivered":
                            job_status_display = f"✅ {job_status_arabic}"
                        else:
                            job_status_display = job_status_arabic
                    
                    # إضافة الدين إلى الجدول
                    if hasattr(self, 'debts_tree'):
                        amount_formatted = self.format_number_english(f"{trans.amount:.2f}")
                        print(f"🔍 [DEBUG] إضافة دين: {date_str}, {amount_formatted} $, {tracking_code}, {device_type}")
                        self.debts_tree.insert("", tk.END, values=(
                            date_str,
                            tracking_code,
                            device_type,
                            f"{amount_formatted} $",
                            trans.description or "دين",
                            job_status_display
                        ))
            
            print(f"✅ [DEBUG] تم إضافة {payment_count} دفعة و {debt_count} دين إلى الجداول")
            
            # تحديث الجداول للتأكد من ظهور البيانات
            if hasattr(self, 'payments_tree'):
                self.payments_tree.update_idletasks()
            if hasattr(self, 'debts_tree'):
                self.debts_tree.update_idletasks()
            
            # حساب الرصيد
            balance = total_debt - total_payment
            
            # تحديث الملخص
            if hasattr(self, 'balance_labels'):
                if 'total_debt' in self.balance_labels:
                    total_debt_formatted = self.format_number_english(f"{total_debt:.2f}")
                    self.balance_labels['total_debt'].configure(text=f"{total_debt_formatted} $")
                if 'total_payment' in self.balance_labels:
                    total_payment_formatted = self.format_number_english(f"{total_payment:.2f}")
                    self.balance_labels['total_payment'].configure(text=f"{total_payment_formatted} $")
                if 'balance' in self.balance_labels:
                    balance_color = "#d32f2f" if balance > 0 else "#388e3c"
                    balance_formatted = self.format_number_english(f"{balance:.2f}")
                    self.balance_labels['balance'].configure(
                        text=f"{balance_formatted} $",
                        text_color=balance_color
                    )
            
            # تحديث نص كشف الحساب (للطباعة)
            statement = self.generate_statement_text(vip, transactions, total_debt, total_payment, balance)
            self.statement_text.delete("1.0", tk.END)
            self.statement_text.insert("1.0", statement)
            
            db.close()
        except Exception as e:
            print(f"خطأ في تحديث كشف الحساب: {e}")
            import traceback
            traceback.print_exc()
    
    def generate_statement_text(self, vip, transactions, total_debt, total_payment, balance):
        """إنشاء نص كشف الحساب للطباعة"""
        db = next(get_db())
        
        try:
            statement = "=" * 70 + "\n"
            statement += f"كشف حساب - {vip.customer.name}\n"
            statement += "=" * 70 + "\n\n"
            statement += f"الاسم: {vip.customer.name}\n"
            statement += f"الهاتف: {vip.customer.phone}\n"
            if vip.customer.email:
                statement += f"البريد: {vip.customer.email}\n"
            statement += f"تاريخ الطباعة: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            statement += "=" * 70 + "\n\n"
            
            # الديون
            statement += "الديون:\n"
            statement += "-" * 70 + "\n"
            debts = [t for t in transactions if t.transaction_type == "debt"]
            if debts:
                statement += f"{'التاريخ':<12} | {'رقم التتبع':<15} | {'نوع الجهاز':<20} | {'المبلغ':>10}\n"
                statement += "-" * 70 + "\n"
                for trans in debts:
                    date_str = trans.created_at.strftime("%Y-%m-%d") if trans.created_at else ""
                    tracking_code = "-"
                    device_type = "-"
                    
                    if trans.maintenance_job_id:
                        job = db.query(MaintenanceJob).filter(MaintenanceJob.id == trans.maintenance_job_id).first()
                        if job:
                            tracking_code = job.tracking_code
                            device_type = job.device_type[:20]  # تقصير النص
                    
                    desc = (trans.description or "دين")[:20]
                    statement += f"{date_str:<12} | {tracking_code:<15} | {device_type:<20} | {trans.amount:>10.2f} $\n"
                    if desc and desc != "دين":
                        statement += f"{'':12} | {'':15} | {desc:<20} | {'':>10}\n"
            else:
                statement += "لا توجد ديون\n"
            
            statement += "\n"
            
            # الدفعات
            statement += "الدفعات:\n"
            statement += "-" * 70 + "\n"
            payments = [t for t in transactions if t.transaction_type == "payment"]
            if payments:
                statement += f"{'التاريخ':<12} | {'المبلغ':>10} | {'طريقة الدفع':<15} | {'الوصف':<25}\n"
                statement += "-" * 70 + "\n"
                for trans in payments:
                    date_str = trans.created_at.strftime("%Y-%m-%d") if trans.created_at else ""
                    method = "كاش" if trans.payment_method == "cash" else "ويش موني" if trans.payment_method == "wish_money" else "أخرى"
                    desc = (trans.description or "دفعة")[:25]
                    statement += f"{date_str:<12} | {trans.amount:>10.2f} $ | {method:<15} | {desc:<25}\n"
            else:
                statement += "لا توجد دفعات\n"
            
            statement += "\n" + "=" * 70 + "\n"
            statement += f"إجمالي الديون: {total_debt:.2f} $\n"
            statement += f"إجمالي المدفوعات: {total_payment:.2f} $\n"
            statement += f"الرصيد الحالي: {balance:.2f} $\n"
            statement += f"حد الائتمان: {vip.credit_limit:.2f} $\n"
            if balance > 0:
                statement += f"\n⚠️ المبلغ المستحق: {balance:.2f} $\n"
            statement += "=" * 70 + "\n"
            statement += f"\nADR ELECTRONICS\n"
            statement += f"شكراً لثقتكم بنا 🙏\n"
            
            return statement
        finally:
            db.close()
    
    def add_vip_customer(self):
        """إضافة عميل مميز جديد"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("إضافة عميل مميز")
        dialog.geometry("400x300")
        dialog.grab_set()
        
        content = ctk.CTkFrame(dialog)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(content, text="اختر العميل:", font=("Arial", 12, "bold")).pack(pady=10)
        
        # قائمة العملاء
        customer_listbox = tk.Listbox(content, height=10)
        customer_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        db = next(get_db())
        customers = db.query(Customer).all()
        
        for customer in customers:
            # التحقق من عدم كونه عميل مميز بالفعل
            existing = db.query(VIPCustomer).filter(VIPCustomer.customer_id == customer.id).first()
            if not existing:
                customer_listbox.insert(tk.END, f"{customer.name} - {customer.phone}")
        
        db.close()
        
        def save():
            selection = customer_listbox.curselection()
            if not selection:
                messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
                return
            
            selected_customer = customers[selection[0]]
            
            try:
                db = next(get_db())
                vip = VIPCustomer(customer_id=selected_customer.id)
                db.add(vip)
                db.commit()
                db.close()
                
                messagebox.showinfo("نجاح", "تم إضافة العميل المميز بنجاح")
                dialog.destroy()
                self.load_vip_customers()
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في إضافة العميل: {str(e)}")
        
        ctk.CTkButton(content, text="حفظ", command=save).pack(pady=10)
    
    def delete_vip_customer(self):
        """حذف عميل مميز"""
        if not hasattr(self, 'current_vip_id') or not self.current_vip_id:
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل للحذف")
            return
        
        try:
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).first()
            
            if not vip:
                db.close()
                messagebox.showerror("خطأ", "لم يتم العثور على العميل المميز")
                return
            
            customer_name = vip.customer.name if vip.customer else "غير معروف"
            
            # التحقق من وجود معاملات مالية
            transactions_count = db.query(AccountTransaction).filter(
                AccountTransaction.vip_customer_id == self.current_vip_id
            ).count()
            
            # التحقق من وجود جداول واتساب
            schedules_count = db.query(WhatsAppSchedule).filter(
                WhatsAppSchedule.vip_customer_id == self.current_vip_id
            ).count()
            
            db.close()
            
            # رسالة تأكيد مع معلومات
            warning_message = f"هل أنت متأكد من حذف العميل المميز:\n\n"
            warning_message += f"الاسم: {customer_name}\n"
            
            if transactions_count > 0:
                warning_message += f"⚠️ يوجد {transactions_count} معاملة مالية مرتبطة بهذا الحساب\n"
                warning_message += "سيتم حذف جميع المعاملات المالية!\n\n"
            
            if schedules_count > 0:
                warning_message += f"⚠️ يوجد {schedules_count} جدول واتساب مرتبط بهذا الحساب\n"
                warning_message += "سيتم حذف جميع الجداول!\n\n"
            
            warning_message += "⚠️ تحذير: لا يمكن التراجع عن هذه العملية!"
            
            if not messagebox.askyesno("تأكيد الحذف", warning_message):
                return
            
            # تأكيد إضافي إذا كان هناك معاملات مالية
            if transactions_count > 0:
                if not messagebox.askyesno("تأكيد نهائي", 
                    f"⚠️ تحذير: يوجد {transactions_count} معاملة مالية!\n\n"
                    "هل أنت متأكد تماماً من حذف هذا الحساب وجميع معاملاته؟\n\n"
                    "هذه العملية لا يمكن التراجع عنها!"):
                    return
            
            # حذف جميع البيانات المرتبطة
            db = next(get_db())
            
            try:
                # حذف المعاملات المالية
                db.query(AccountTransaction).filter(
                    AccountTransaction.vip_customer_id == self.current_vip_id
                ).delete()
                
                # حذف جداول واتساب
                db.query(WhatsAppSchedule).filter(
                    WhatsAppSchedule.vip_customer_id == self.current_vip_id
                ).delete()
                
                # حذف الحساب المميز
                db.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).delete()
                
                db.commit()
                db.close()
                
                messagebox.showinfo("نجاح", f"✅ تم حذف العميل المميز '{customer_name}' بنجاح")
                
                # إعادة تعيين البيانات
                self.current_vip_id = None
                self.name_label.configure(text="-")
                self.phone_label.configure(text="-")
                
                # مسح الجداول
                if hasattr(self, 'orders_tree'):
                    for item in self.orders_tree.get_children():
                        self.orders_tree.delete(item)
                
                if hasattr(self, 'payments_tree'):
                    for item in self.payments_tree.get_children():
                        self.payments_tree.delete(item)
                
                if hasattr(self, 'debts_tree'):
                    for item in self.debts_tree.get_children():
                        self.debts_tree.delete(item)
                
                # تحديث قائمة العملاء
                self.load_vip_customers()
                
            except Exception as e:
                db.rollback()
                db.close()
                raise e
                
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حذف العميل المميز: {str(e)}")
            import traceback
            print(traceback.format_exc())
    
    def save_customer_settings(self):
        """حفظ إعدادات العميل - تم تبسيط الواجهة"""
        # تم تبسيط الواجهة لعرض اسم العميل ورقم الهاتف فقط
        # لا توجد إعدادات للحفظ في هذه الصفحة
        messagebox.showinfo("معلومة", "تم تبسيط الواجهة - لا توجد إعدادات للحفظ في هذه الصفحة")
    
    def add_free_payment(self):
        """إضافة دفعة حرة (بدون ربط بطلب محدد)"""
        if not hasattr(self, 'current_vip_id'):
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
            return
        
        # فتح نافذة إضافة دفعة حرة
        dialog = ctk.CTkToplevel(self)
        dialog.title("إضافة دفعة حرة")
        dialog.geometry("400x350")
        dialog.grab_set()
        
        content = ctk.CTkFrame(dialog)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(content, text="المبلغ المدفوع:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        amount_entry = ctk.CTkEntry(content, width=200)
        amount_entry.pack(anchor=tk.W, padx=10, pady=5)
        
        ctk.CTkLabel(content, text="طريقة الدفع:", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        method_combo = ctk.CTkComboBox(content, values=["كاش", "ويش موني"], width=200)
        method_combo.pack(anchor=tk.W, padx=10, pady=5)
        method_combo.set("كاش")
        
        ctk.CTkLabel(content, text="الوصف (اختياري):", font=("Arial", 12)).pack(anchor=tk.W, padx=10, pady=5)
        desc_text = ctk.CTkTextbox(content, height=100)
        desc_text.pack(fill=tk.X, padx=10, pady=5)
        desc_text.insert("1.0", "دفعة حرة")
        
        def save():
            try:
                amount = float(amount_entry.get())
                if amount <= 0:
                    messagebox.showwarning("تحذير", "المبلغ يجب أن يكون أكبر من صفر")
                    return
                
                payment_method = "cash" if method_combo.get() == "كاش" else "wish_money"
                description = desc_text.get("1.0", tk.END).strip() or "دفعة حرة"
                
                db = next(get_db())
                
                # حساب الرصيد الحالي قبل إضافة الدفعة
                from sqlalchemy import func, case
                totals = db.query(
                    func.sum(case((AccountTransaction.transaction_type == "debt", AccountTransaction.amount), else_=0)).label('total_debt'),
                    func.sum(case((AccountTransaction.transaction_type == "payment", AccountTransaction.amount), else_=0)).label('total_payment')
                ).filter(AccountTransaction.vip_customer_id == self.current_vip_id).first()
                
                total_debt = totals.total_debt or 0
                total_payment = totals.total_payment or 0
                current_balance = total_debt - total_payment
                
                # إضافة المعاملة المالية في AccountTransaction
                from database.models import AccountTransaction
                transaction = AccountTransaction(
                    vip_customer_id=self.current_vip_id,
                    transaction_type="payment",
                    amount=amount,
                    payment_method=payment_method,
                    description=description
                )
                db.add(transaction)
                db.commit()
                
                # حساب الرصيد الجديد بعد إضافة الدفعة
                new_balance = current_balance - amount
                
                # عرض رسالة تأكيد مع معلومات الرصيد
                balance_info = f"\nالرصيد قبل الدفعة: {current_balance:.2f} $\n"
                balance_info += f"الرصيد بعد الدفعة: {new_balance:.2f} $"
                
                if new_balance <= 0:
                    balance_info += "\n✅ تم تسديد جميع الديون!"
                else:
                    balance_info += f"\n⚠️ المبلغ المتبقي: {new_balance:.2f} $"
                
                db.close()
                
                messagebox.showinfo("نجاح", f"✅ تم إضافة دفعة {amount:.2f} $ بنجاح{balance_info}")
                dialog.destroy()
                
                # تحديث البيانات
                if hasattr(self, 'current_vip_id'):
                    db2 = next(get_db())
                    vip = db2.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).first()
                    if vip:
                        self.load_customer_orders(vip.customer_id)
                        self.update_statement(self.current_vip_id)
                    db2.close()
                
            except ValueError:
                messagebox.showerror("خطأ", "الرجاء إدخال مبلغ صحيح")
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في إضافة الدفعة: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        btn_frame = ctk.CTkFrame(content)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkButton(btn_frame, text="إلغاء", command=dialog.destroy, fg_color="#6c757d", hover_color="#5a6268").pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(btn_frame, text="حفظ", command=save, fg_color="#17a2b8", hover_color="#138496").pack(side=tk.RIGHT, padx=5)
    
    def add_whatsapp_schedule(self):
        """إضافة جدول واتساب"""
        if not hasattr(self, 'current_vip_id'):
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
            return
        
        # إضافة جدول واتساب بسيط
        dialog = ctk.CTkToplevel(self)
        dialog.title("إضافة جدول واتساب")
        dialog.geometry("400x300")
        dialog.grab_set()
        
        content = ctk.CTkFrame(dialog)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(content, text="نوع الرسالة:").pack(anchor=tk.W, padx=10, pady=5)
        message_type_combo = ctk.CTkComboBox(content, values=["تحديث حالة", "تذكير دين", "إشعار عام"], width=200)
        message_type_combo.pack(anchor=tk.W, padx=10, pady=5)
        
        ctk.CTkLabel(content, text="وقت الإرسال (HH:MM):").pack(anchor=tk.W, padx=10, pady=5)
        time_entry = ctk.CTkEntry(content, width=200, placeholder_text="مثال: 09:00")
        time_entry.pack(anchor=tk.W, padx=10, pady=5)
        
        def save():
            try:
                db = next(get_db())
                schedule = WhatsAppSchedule(
                    vip_customer_id=self.current_vip_id,
                    message_type=message_type_combo.get(),
                    send_time=time_entry.get(),
                    is_active=True
                )
                db.add(schedule)
                db.commit()
                db.close()
                
                messagebox.showinfo("نجاح", "تم إضافة جدول واتساب بنجاح")
                dialog.destroy()
                self.load_whatsapp_schedules(self.current_vip_id)
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في إضافة الجدول: {str(e)}")
        
        ctk.CTkButton(content, text="حفظ", command=save).pack(pady=10)
    
    def edit_whatsapp_schedule(self):
        """تعديل جدول واتساب"""
        messagebox.showinfo("معلومة", "يمكنك حذف الجدول الحالي وإضافة جدول جديد")
    
    def delete_whatsapp_schedule(self):
        """حذف جدول واتساب"""
        selection = self.schedules_listbox.curselection()
        if not selection:
            messagebox.showwarning("تحذير", "الرجاء اختيار جدول للحذف")
            return
        
        if messagebox.askyesno("تأكيد", "هل تريد حذف هذا الجدول؟"):
            try:
                # هذا يتطلب حفظ معرف الجدول مع كل عنصر في القائمة
                messagebox.showinfo("معلومة", "سيتم تفعيل هذه الميزة في التحديثات القادمة")
            except Exception as e:
                messagebox.showerror("خطأ", f"فشل في حذف الجدول: {str(e)}")
    
    def send_whatsapp_now(self):
        """إرسال رسالة واتساب فورية"""
        if not hasattr(self, 'current_vip_id'):
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
            return
        
        try:
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).first()
            db.close()
            
            if not vip or not vip.whatsapp_number:
                messagebox.showwarning("تحذير", "العميل لا يملك رقم واتساب")
                return
            
            import webbrowser
            import urllib.parse
            
            # إنشاء رابط واتساب
            phone = vip.whatsapp_number.replace("+", "").replace(" ", "")
            message = f"مرحباً {vip.customer.name}، هذا من شركة ADR Electronics"
            whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
            
            webbrowser.open(whatsapp_url)
            messagebox.showinfo("نجاح", f"تم فتح واتساب لإرسال رسالة إلى:\n{vip.whatsapp_number}")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في فتح واتساب: {str(e)}")
    
    def send_statement_whatsapp(self):
        """إرسال كشف الحساب عبر واتساب"""
        if not hasattr(self, 'current_vip_id'):
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
            return
        
        try:
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).first()
            
            if not vip:
                db.close()
                messagebox.showerror("خطأ", "لم يتم العثور على العميل")
                return
            
            if not vip.whatsapp_number:
                db.close()
                messagebox.showwarning("تحذير", "العميل لا يملك رقم واتساب مسجل")
                return
            
            # جلب البيانات
            transactions = db.query(AccountTransaction).filter(
                AccountTransaction.vip_customer_id == self.current_vip_id
            ).order_by(AccountTransaction.created_at.desc()).all()
            
            total_debt = sum(t.amount for t in transactions if t.transaction_type == "debt")
            total_payment = sum(t.amount for t in transactions if t.transaction_type == "payment")
            balance = total_debt - total_payment
            
            db.close()
            
            # إنشاء رسالة كشف الحساب محسّنة
            message = f"📋 كشف حساب - ADR ELECTRONICS\n"
            message += "=" * 30 + "\n"
            message += f"👤 العميل: {vip.customer.name}\n"
            message += f"📞 الهاتف: {vip.customer.phone}\n"
            message += f"📅 تاريخ الكشف: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            message += "=" * 30 + "\n\n"
            
            # عرض جميع الديون
            debts = [t for t in transactions if t.transaction_type == "debt"]
            if debts:
                message += "📋 الديون:\n"
                message += "-" * 30 + "\n"
                for trans in debts:
                    date_str = trans.created_at.strftime("%Y-%m-%d") if trans.created_at else ""
                    desc = trans.description or "دين"
                    # تقصير الوصف إذا كان طويلاً
                    if len(desc) > 40:
                        desc = desc[:37] + "..."
                    message += f"📅 {date_str}\n"
                    message += f"   +{trans.amount:.2f} $\n"
                    message += f"   {desc}\n\n"
            else:
                message += "📋 الديون: لا توجد ديون\n\n"
            
            # عرض جميع الدفعات
            payments = [t for t in transactions if t.transaction_type == "payment"]
            if payments:
                message += "💵 الدفعات:\n"
                message += "-" * 30 + "\n"
                for trans in payments:
                    date_str = trans.created_at.strftime("%Y-%m-%d") if trans.created_at else ""
                    method = "كاش" if trans.payment_method == "cash" else "ويش موني" if trans.payment_method == "wish_money" else "غير محدد"
                    desc = trans.description or "دفعة"
                    # تقصير الوصف إذا كان طويلاً
                    if len(desc) > 40:
                        desc = desc[:37] + "..."
                    message += f"📅 {date_str}\n"
                    message += f"   -{trans.amount:.2f} $ ({method})\n"
                    message += f"   {desc}\n\n"
            else:
                message += "💵 الدفعات: لا توجد دفعات\n\n"
            
            message += "=" * 30 + "\n"
            message += "💰 الملخص:\n"
            message += f"   إجمالي الديون: {total_debt:.2f} $\n"
            message += f"   إجمالي المدفوعات: {total_payment:.2f} $\n"
            message += f"   الرصيد الحالي: {balance:.2f} $\n"
            
            if balance > 0:
                message += f"\n⚠️ المبلغ المستحق: {balance:.2f} $\n"
                message += "يرجى تسديد المبلغ المستحق في أقرب وقت ممكن.\n"
            elif balance < 0:
                message += f"\n✅ رصيد إضافي: {abs(balance):.2f} $\n"
            else:
                message += "\n✅ الحساب متوازن - لا يوجد مبلغ مستحق\n"
            
            message += "\n" + "=" * 30 + "\n"
            message += "ADR ELECTRONICS\n"
            message += "شكراً لثقتكم بنا 🙏\n"
            message += "للاستفسار: " + (vip.customer.phone or "اتصل بنا")
            
            # فتح واتساب
            import webbrowser
            import urllib.parse
            
            phone = vip.whatsapp_number.replace("+", "").replace(" ", "").strip()
            if not phone.startswith("961"):
                # إذا لم يبدأ بـ 961، أضفه
                phone = phone.lstrip("0")
                if not phone.startswith("961"):
                    phone = "961" + phone
            
            whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
            webbrowser.open(whatsapp_url)
            
            messagebox.showinfo("نجاح", f"تم فتح واتساب لإرسال كشف الحساب إلى:\n{vip.whatsapp_number}")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في إرسال كشف الحساب: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def print_statement(self):
        """طباعة كشف الحساب"""
        if not hasattr(self, 'current_vip_id'):
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
            return
        
        try:
            from tkinter import filedialog
            import os
            
            # الحصول على كشف الحساب من النص المخفي
            statement_text = self.statement_text.get("1.0", tk.END)
            
            if not statement_text.strip():
                messagebox.showwarning("تحذير", "لا توجد بيانات لعرضها")
                return
            
            # حفظ كشف الحساب في ملف نصي
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).first()
            db.close()
            
            if not vip:
                messagebox.showerror("خطأ", "لم يتم العثور على العميل")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("ملف نصي", "*.txt"), ("جميع الملفات", "*.*")],
                initialfile=f"كشف_حساب_{vip.customer.name.replace(' ', '_')}.txt"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(statement_text)
                
                messagebox.showinfo("نجاح", f"تم حفظ كشف الحساب في:\n{filename}")
                os.startfile(filename)  # فتح الملف
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في حفظ كشف الحساب: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def on_debt_double_click(self, event):
        """معالجة النقر المزدوج على جدول الديون"""
        selection = self.debts_tree.selection()
        if not selection:
            return
        
        # يمكن إضافة وظيفة للتعديل أو الحذف لاحقاً
        pass
    
    def add_debt_from_delivered_job(self):
        """إضافة دين من طلب مسلم"""
        if not hasattr(self, 'current_vip_id'):
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
            return
        
        try:
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).first()
            
            if not vip:
                db.close()
                messagebox.showerror("خطأ", "لم يتم العثور على العميل")
                return
            
            # جلب الطلبات المسلمة غير المدفوعة
            delivered_jobs = db.query(MaintenanceJob).filter(
                MaintenanceJob.customer_id == vip.customer_id,
                MaintenanceJob.status == "delivered",
                MaintenanceJob.payment_status == "unpaid"
            ).order_by(MaintenanceJob.received_at.desc()).all()
            
            db.close()
            
            if not delivered_jobs:
                messagebox.showinfo("معلومة", "لا توجد طلبات مسلمة غير مدفوعة")
                return
            
            # فتح نافذة اختيار الطلب
            dialog = ctk.CTkToplevel(self)
            dialog.title("إضافة دين من طلب مسلم")
            dialog.geometry("600x400")
            dialog.grab_set()
            
            content = ctk.CTkFrame(dialog)
            content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            ctk.CTkLabel(content, text="اختر طلب لإضافة دين:", font=("Arial", 12, "bold")).pack(pady=10)
            
            # جدول الطلبات
            jobs_frame = ctk.CTkFrame(content)
            jobs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            jobs_columns = ("tracking_code", "device_type", "amount", "date")
            jobs_tree = ttk.Treeview(jobs_frame, columns=jobs_columns, show="headings", height=10)
            jobs_tree.heading("tracking_code", text="رقم التتبع")
            jobs_tree.heading("device_type", text="نوع الجهاز")
            jobs_tree.heading("amount", text="المبلغ")
            jobs_tree.heading("date", text="التاريخ")
            
            jobs_tree.column("tracking_code", width=120)
            jobs_tree.column("device_type", width=200)
            jobs_tree.column("amount", width=100)
            jobs_tree.column("date", width=120)
            
            jobs_scrollbar = ttk.Scrollbar(jobs_frame, orient=tk.VERTICAL, command=jobs_tree.yview)
            jobs_tree.configure(yscroll=jobs_scrollbar.set)
            
            jobs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            jobs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # إضافة الطلبات
            db_check = next(get_db())
            for job in delivered_jobs:
                amount = job.final_cost or job.estimated_cost or 0
                if amount <= 0:
                    continue  # تخطي الطلبات بدون مبلغ
                
                date_str = job.received_at.strftime("%Y-%m-%d") if job.received_at else ""
                
                # التحقق من وجود دين مسبق
                existing_debt = db_check.query(AccountTransaction).filter(
                    AccountTransaction.maintenance_job_id == job.id,
                    AccountTransaction.transaction_type == "debt"
                ).first()
                
                if existing_debt:
                    continue  # تخطي الطلبات التي لها دين مسبق
                
                amount_formatted = self.format_number_english(f"{amount:.2f}")
                jobs_tree.insert("", tk.END, values=(
                    job.tracking_code,
                    job.device_type,
                    f"{amount_formatted} $",
                    date_str
                ), tags=(job.id,))
            
            db_check.close()
            
            def add_selected_debt():
                selection = jobs_tree.selection()
                if not selection:
                    messagebox.showwarning("تحذير", "الرجاء اختيار طلب")
                    return
                
                item = jobs_tree.item(selection[0])
                job_id = item['tags'][0]
                
                try:
                    db = next(get_db())
                    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
                    
                    if not job:
                        db.close()
                        messagebox.showerror("خطأ", "لم يتم العثور على الطلب")
                        return
                    
                    amount = job.final_cost or job.estimated_cost or 0
                    
                    if amount <= 0:
                        db.close()
                        messagebox.showwarning("تحذير", "المبلغ غير صحيح")
                        return
                    
                    # التحقق من عدم وجود دين مسبق
                    existing_debt = db.query(AccountTransaction).filter(
                        AccountTransaction.maintenance_job_id == job_id,
                        AccountTransaction.transaction_type == "debt"
                    ).first()
                    
                    if existing_debt:
                        db.close()
                        messagebox.showinfo("معلومة", "تم إضافة الدين مسبقاً لهذا الطلب")
                        return
                    
                    # إضافة الدين
                    transaction = AccountTransaction(
                        vip_customer_id=self.current_vip_id,
                        maintenance_job_id=job_id,
                        transaction_type="debt",
                        amount=amount,
                        description=f"دين من طلب الصيانة رقم {job.tracking_code} - {job.device_type}"
                    )
                    
                    db.add(transaction)
                    db.commit()
                    db.close()
                    
                    messagebox.showinfo("نجاح", f"تم إضافة دين {self.format_number_english(amount):.2f} $ بنجاح")
                    dialog.destroy()
                    
                    # تحديث البيانات
                    self.update_statement(self.current_vip_id)
                    
                except Exception as e:
                    messagebox.showerror("خطأ", f"فشل في إضافة الدين: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            btn_frame = ctk.CTkFrame(content)
            btn_frame.pack(fill=tk.X, padx=10, pady=10)
            
            ctk.CTkButton(btn_frame, text="إلغاء", command=dialog.destroy, fg_color="#6c757d").pack(side=tk.LEFT, padx=5)
            ctk.CTkButton(btn_frame, text="إضافة الدين", command=add_selected_debt, fg_color="#28a745").pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في تحميل الطلبات: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def email_statement(self):
        """إرسال كشف الحساب بالبريد"""
        if not hasattr(self, 'current_vip_id'):
            messagebox.showwarning("تحذير", "الرجاء اختيار عميل")
            return
        
        try:
            db = next(get_db())
            vip = db.query(VIPCustomer).filter(VIPCustomer.id == self.current_vip_id).first()
            db.close()
            
            if not vip or not vip.customer.email:
                messagebox.showwarning("تحذير", "العميل لا يملك عنوان بريد إلكتروني")
                return
            
            import webbrowser
            import urllib.parse
            
            subject = f"كشف حساب - {vip.customer.name}"
            body = self.statement_text.get("1.0", tk.END)
            
            mailto_link = f"mailto:{vip.customer.email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
            webbrowser.open(mailto_link)
            
            messagebox.showinfo("نجاح", f"تم فتح تطبيق البريد لإرسال كشف الحساب إلى:\n{vip.customer.email}")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في إرسال كشف الحساب: {str(e)}")
    
    def search_customers(self):
        """بحث عن عملاء"""
        search_term = self.search_entry.get().strip()
        if not search_term:
            self.load_vip_customers()
            return
        
        try:
            db = next(get_db())
            vip_customers = db.query(VIPCustomer).join(Customer).filter(
                Customer.name.ilike(f"%{search_term}%")
            ).all()
            
            # مسح القائمة
            for item in self.customers_tree.get_children():
                self.customers_tree.delete(item)
            
            # إضافة النتائج
            for vip in vip_customers:
                self.customers_tree.insert("", tk.END, values=(vip.customer.name,), tags=(vip.id,))
            
            db.close()
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل في البحث: {str(e)}")

