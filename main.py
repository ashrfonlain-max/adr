"""
نظام إدارة الصيانة - ADR Maintenance System
"""

import sys
import os
import customtkinter as ctk
from sqlalchemy import inspect, text, exists

from database.connection import init_db, get_db
from gui.maintenance_window import MaintenanceFrame
from database.models import User, UserRole
from utils.auth import hash_password
from utils.logger import logger

class MaintenanceApp:
    def __init__(self):
        # تهيئة قاعدة البيانات أولاً (للموثوقية)
        logger.info("🔄 جاري تهيئة قاعدة البيانات...")
        init_db()
        
        # إنشاء مستخدم افتراضي إذا لم يكن موجوداً
        self.create_default_user()
        self.current_user = self.get_default_user()
        
        # تهيئة الواجهة
        self.setup_ui()
    
    def create_default_user(self):
        """إنشاء مستخدم افتراضي - محسّن للأداء"""
        db = next(get_db())
        try:
            self.ensure_users_schema(db)
            # استخدام exists() بدلاً من count() - أسرع بكثير
            if not db.query(exists().where(User.id.isnot(None))).scalar():
                # استخدام كلمة المرور من متغيرات البيئة
                from config import ADMIN_DEFAULT_PASSWORD
                admin = User(
                    username="admin",
                    password_hash=hash_password(ADMIN_DEFAULT_PASSWORD),
                    full_name="مدير النظام",
                    role=UserRole.ADMIN,
                    is_active=True
                )
                db.add(admin)
                db.commit()
                logger.info("✅ تم إنشاء المستخدم الافتراضي بنجاح")
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء المستخدم الافتراضي: {e}", exc_info=True)
        finally:
            db.close()

    def ensure_users_schema(self, db):
        """ضمان وجود الأعمدة المطلوبة في جدول المستخدمين"""
        try:
            inspector = inspect(db.bind)
            columns = [col['name'] for col in inspector.get_columns('users')]
            if 'last_login_at' not in columns:
                db.execute(text("ALTER TABLE users ADD COLUMN last_login_at DATETIME"))
                db.commit()
        except Exception as e:
            logger.warning(f"⚠️ تعذر تحديث جدول المستخدمين: {e}")
    
    def setup_ui(self):
        """إعداد واجهة المستخدم (بدون شاشة تسجيل الدخول)"""
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("نظام إدارة الصيانة")
        
        # جعل النافذة تملأ الشاشة بالكامل
        try:
            # Windows
            self.root.state('zoomed')
        except:
            try:
                # Linux
                self.root.attributes('-zoomed', True)
            except:
                # Fallback: استخدام حجم الشاشة الكامل
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # تكوين grid للنافذة الرئيسية
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        self.open_main_window()
        self.root.mainloop()

    def open_main_window(self):
        """فتح الواجهة الرئيسية بعد تسجيل الدخول"""
        for widget in self.root.winfo_children():
            widget.destroy()

        maintenance_frame = MaintenanceFrame(self.root, current_user=self.current_user)
        self.maintenance_frame = maintenance_frame
        # جعل الإطار يملأ الشاشة بالكامل بدون padding
        maintenance_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)

    def get_default_user(self):
        """الحصول على المستخدم الافتراضي (admin) إن وجد"""
        db = next(get_db())
        try:
            return db.query(User).filter(User.username == "admin").first()
        finally:
            db.close()

if __name__ == "__main__":
    app = MaintenanceApp()
