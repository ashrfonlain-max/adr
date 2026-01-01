"""
نظام النسخ الاحتياطي التلقائي كل 10 دقائق على USB/فلاشة ميموري
"""

import os
import sys
import time
import threading
import schedule
from datetime import datetime
from pathlib import Path
import logging

# إضافة مسار النظام
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.backup_system import BackupSystem
from utils.external_drive_backup import ExternalDriveBackup
import config

class USBAutoBackupScheduler:
    """منظم النسخ الاحتياطي التلقائي على USB كل 10 دقائق"""
    
    def __init__(self, backup_interval_minutes=10, usb_drive_path=None):
        self.backup_interval = backup_interval_minutes
        self.backup_interval_minutes = backup_interval_minutes  # للتوافق
        self.usb_drive_path = usb_drive_path
        self.backup_system = BackupSystem()
        self.external_drive = ExternalDriveBackup()
        self.is_running = False
        self.thread = None
        self.last_backup_time = None
        self.last_backup_status = None
        
        # إعداد نظام السجلات
        self.setup_logging()
        
    def setup_logging(self):
        """إعداد نظام السجلات"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"usb_auto_backup_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def detect_usb_drive(self):
        """اكتشاف محرك USB تلقائياً"""
        try:
            # إذا تم تحديد مسار USB مسبقاً، استخدمه
            if self.usb_drive_path and os.path.exists(self.usb_drive_path):
                return self.usb_drive_path
            
            # اكتشاف محركات USB المتاحة
            drives = self.external_drive.detect_external_drives()
            
            if not drives:
                self.logger.warning("⚠️ لم يتم العثور على أي محرك USB متصل")
                return None
            
            # البحث عن محرك قابل للكتابة
            writable_drives = [d for d in drives if d.get("writable", False)]
            
            if not writable_drives:
                self.logger.warning("⚠️ لا توجد محركات USB قابلة للكتابة")
                return None
            
            # استخدام أول محرك قابل للكتابة
            selected_drive = writable_drives[0]
            drive_path = selected_drive.get("path")
            drive_name = selected_drive.get("name", "Unknown")
            
            self.logger.info(f"✅ تم اكتشاف محرك USB: {drive_name} ({drive_path})")
            return drive_path
            
        except Exception as e:
            self.logger.error(f"❌ خطأ في اكتشاف محرك USB: {str(e)}")
            return None
    
    def create_usb_backup(self):
        """إنشاء نسخة احتياطية على USB"""
        try:
            self.logger.info("🔄 بدء النسخ الاحتياطي التلقائي على USB...")
            
            # اكتشاف محرك USB
            usb_path = self.detect_usb_drive()
            
            if not usb_path:
                error_msg = "لم يتم العثور على محرك USB متصل"
                self.logger.error(f"❌ {error_msg}")
                self.last_backup_status = {
                    "success": False,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
                return self.last_backup_status
            
            # التحقق من المساحة المتاحة
            space_info = self.external_drive.get_drive_space_info(usb_path)
            if space_info.get("success"):
                free_gb = space_info.get("free_gb", 0)
                if free_gb < 0.1:  # أقل من 100 MB
                    error_msg = f"مساحة غير كافية على USB: {free_gb:.2f} GB متاح"
                    self.logger.error(f"❌ {error_msg}")
                    self.last_backup_status = {
                        "success": False,
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat()
                    }
                    return self.last_backup_status
            
            # إنشاء النسخة الاحتياطية
            self.logger.info("📦 جاري إنشاء النسخة الاحتياطية...")
            backup_result = self.backup_system.create_automated_backup()
            
            if not backup_result.get("success", False):
                error_msg = backup_result.get("error", "خطأ غير معروف في إنشاء النسخة الاحتياطية")
                self.logger.error(f"❌ {error_msg}")
                self.last_backup_status = {
                    "success": False,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
                return self.last_backup_status
            
            backup_path = backup_result.get("backup_path")
            backup_size = backup_result.get("size", 0)
            
            self.logger.info(f"✅ تم إنشاء النسخة الاحتياطية بنجاح! الحجم: {backup_size / (1024*1024):.2f} MB")
            
            # نسخ النسخة الاحتياطية إلى USB
            self.logger.info(f"💾 جاري نسخ النسخة الاحتياطية إلى USB ({usb_path})...")
            copy_result = self.external_drive.copy_backup_to_drive(backup_path, usb_path)
            
            if copy_result.get("success", False):
                target_path = copy_result.get("target_path", "غير محدد")
                self.logger.info(f"✅ تم نسخ النسخة الاحتياطية إلى USB بنجاح!")
                self.logger.info(f"📁 مسار النسخة على USB: {target_path}")
                
                # تنظيف النسخ القديمة على USB (أكثر من 7 أيام)
                self.cleanup_old_usb_backups(usb_path, keep_days=7)
                
                self.last_backup_time = datetime.now()
                self.last_backup_status = {
                    "success": True,
                    "backup_path": backup_path,
                    "usb_path": target_path,
                    "size": backup_size,
                    "timestamp": self.last_backup_time.isoformat()
                }
                
                return self.last_backup_status
            else:
                error_msg = copy_result.get("error", "خطأ غير معروف في نسخ النسخة الاحتياطية إلى USB")
                self.logger.error(f"❌ {error_msg}")
                self.last_backup_status = {
                    "success": False,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat()
                }
                return self.last_backup_status
                
        except Exception as e:
            error_msg = f"خطأ في النسخ الاحتياطي على USB: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            self.last_backup_status = {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
            return self.last_backup_status
    
    def cleanup_old_usb_backups(self, usb_path, keep_days=7):
        """تنظيف النسخ القديمة على USB"""
        try:
            backups_info = self.external_drive.list_backups_on_drive(usb_path)
            
            if not backups_info.get("success", False):
                return
            
            backups = backups_info.get("backups", [])
            if not backups:
                return
            
            cutoff_time = time.time() - (keep_days * 24 * 60 * 60)
            deleted_count = 0
            
            for backup in backups:
                modified_time = backup.get("modified_time", 0)
                if modified_time < cutoff_time:
                    backup_path = backup.get("file_path")
                    try:
                        Path(backup_path).unlink()
                        deleted_count += 1
                        self.logger.info(f"🧹 تم حذف نسخة قديمة: {backup.get('file_name')}")
                    except Exception as e:
                        self.logger.warning(f"⚠️ تعذر حذف النسخة القديمة {backup.get('file_name')}: {str(e)}")
            
            if deleted_count > 0:
                self.logger.info(f"🧹 تم تنظيف {deleted_count} نسخة قديمة من USB")
                
        except Exception as e:
            self.logger.warning(f"⚠️ خطأ في تنظيف النسخ القديمة: {str(e)}")
    
    def start_scheduler(self):
        """بدء منظم النسخ الاحتياطي"""
        try:
            self.logger.info("🚀 بدء منظم النسخ الاحتياطي التلقائي على USB...")
            self.logger.info(f"⏰ النسخ الاحتياطي كل {self.backup_interval} دقيقة")
            
            # جدولة النسخ الاحتياطي
            schedule.every(self.backup_interval).minutes.do(self.create_usb_backup)
            
            # إنشاء نسخة احتياطية فورية عند البدء
            self.logger.info("📦 إنشاء نسخة احتياطية فورية...")
            self.create_usb_backup()
            
            self.is_running = True
            
            # تشغيل المنظم في خيط منفصل
            def run_scheduler():
                while self.is_running:
                    schedule.run_pending()
                    time.sleep(30)  # فحص كل 30 ثانية
            
            self.thread = threading.Thread(target=run_scheduler, daemon=True)
            self.thread.start()
            
            self.logger.info("✅ تم بدء منظم النسخ الاحتياطي التلقائي على USB بنجاح!")
            self.logger.info("💡 تأكد من أن USB متصل دائماً لضمان عمل النسخ التلقائي")
            
        except Exception as e:
            self.logger.error(f"❌ خطأ في بدء منظم النسخ الاحتياطي: {str(e)}")
    
    def stop_scheduler(self):
        """إيقاف منظم النسخ الاحتياطي"""
        try:
            self.logger.info("⏹️ إيقاف منظم النسخ الاحتياطي...")
            self.is_running = False
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            
            self.logger.info("✅ تم إيقاف منظم النسخ الاحتياطي")
            
        except Exception as e:
            self.logger.error(f"❌ خطأ في إيقاف منظم النسخ الاحتياطي: {str(e)}")
    
    def get_next_backup_time(self):
        """الحصول على وقت النسخة الاحتياطية التالية"""
        try:
            if schedule.jobs:
                next_run = schedule.jobs[0].next_run
                return next_run.strftime("%Y-%m-%d %H:%M:%S")
            return "غير محدد"
        except:
            return "غير محدد"
    
    def get_backup_status(self):
        """الحصول على حالة النسخ الاحتياطي"""
        return {
            "is_running": self.is_running,
            "interval_minutes": self.backup_interval,
            "next_backup": self.get_next_backup_time(),
            "last_backup_time": self.last_backup_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_backup_time else "لم يتم بعد",
            "last_backup_status": self.last_backup_status,
            "usb_drive_path": self.usb_drive_path or "اكتشاف تلقائي",
            "thread_alive": self.thread.is_alive() if self.thread else False
        }

# متغير عام للمنظم
usb_auto_backup_scheduler = None

def start_usb_auto_backup(interval_minutes=10, usb_drive_path=None):
    """بدء النسخ الاحتياطي التلقائي على USB"""
    global usb_auto_backup_scheduler
    
    if usb_auto_backup_scheduler is None:
        usb_auto_backup_scheduler = USBAutoBackupScheduler(backup_interval_minutes=interval_minutes, usb_drive_path=usb_drive_path)
    
    usb_auto_backup_scheduler.start_scheduler()
    return usb_auto_backup_scheduler

def stop_usb_auto_backup():
    """إيقاف النسخ الاحتياطي التلقائي على USB"""
    global usb_auto_backup_scheduler
    
    if usb_auto_backup_scheduler:
        usb_auto_backup_scheduler.stop_scheduler()
        usb_auto_backup_scheduler = None

def get_usb_auto_backup_status():
    """الحصول على حالة النسخ الاحتياطي التلقائي على USB"""
    global usb_auto_backup_scheduler
    
    if usb_auto_backup_scheduler:
        return usb_auto_backup_scheduler.get_backup_status()
    else:
        return {
            "is_running": False,
            "interval_minutes": 0,
            "next_backup": "غير محدد",
            "last_backup_time": "لم يتم بعد",
            "last_backup_status": None,
            "usb_drive_path": "غير محدد",
            "thread_alive": False
        }

