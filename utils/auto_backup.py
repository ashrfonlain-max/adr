"""
نظام النسخ الاحتياطي التلقائي كل ربع ساعة (15 دقيقة)
"""

import os
import sys
import time
import threading
import schedule
from datetime import datetime, timedelta
from pathlib import Path
import logging

# إضافة مسار النظام
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.backup_system import BackupSystem
import config

class AutoBackupScheduler:
    """منظم النسخ الاحتياطي التلقائي"""
    
    def __init__(self, backup_interval_minutes=None):
        # استخدام الإعداد من config أو القيمة الافتراضية 15 دقيقة
        if backup_interval_minutes is None:
            backup_interval_minutes = getattr(config, 'BACKUP_INTERVAL_MINUTES', 15)
        self.backup_interval = backup_interval_minutes
        self.backup_system = BackupSystem()
        self.is_running = False
        self.thread = None
        
        # إعداد نظام السجلات
        self.setup_logging()
        
    def setup_logging(self):
        """إعداد نظام السجلات"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"auto_backup_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def create_auto_backup(self):
        """إنشاء نسخة احتياطية تلقائية"""
        try:
            self.logger.info("🔄 بدء النسخ الاحتياطي التلقائي...")
            
            # إنشاء النسخة الاحتياطية
            result = self.backup_system.create_automated_backup()
            
            if result.get("success", False):
                backup_path = result.get("backup_path", "غير محدد")
                backup_size = result.get("size", 0)
                
                self.logger.info(f"✅ تم إنشاء النسخة الاحتياطية التلقائية بنجاح!")
                self.logger.info(f"📁 مسار النسخة: {backup_path}")
                self.logger.info(f"📊 حجم النسخة: {backup_size / (1024*1024):.2f} MB")
                
                # تنظيف النسخ القديمة (أكثر من 7 أيام)
                cleanup_result = self.backup_system.cleanup_old_backups(keep_days=7)
                if cleanup_result.get("success", False):
                    deleted_count = cleanup_result.get("deleted_count", 0)
                    freed_space = cleanup_result.get("freed_space_mb", 0)
                    self.logger.info(f"🧹 تم تنظيف {deleted_count} نسخة قديمة، تم تحرير {freed_space:.2f} MB")
                
            else:
                error_msg = result.get("error", "خطأ غير معروف")
                self.logger.error(f"❌ فشل في إنشاء النسخة الاحتياطية التلقائية: {error_msg}")
                
        except Exception as e:
            self.logger.error(f"❌ خطأ في النسخ الاحتياطي التلقائي: {str(e)}")
    
    def start_scheduler(self):
        """بدء منظم النسخ الاحتياطي"""
        try:
            self.logger.info("🚀 بدء منظم النسخ الاحتياطي التلقائي...")
            self.logger.info(f"⏰ النسخ الاحتياطي كل {self.backup_interval} دقيقة")
            
            # جدولة النسخ الاحتياطي
            schedule.every(self.backup_interval).minutes.do(self.create_auto_backup)
            
            # إنشاء نسخة احتياطية فورية عند البدء
            self.logger.info("📦 إنشاء نسخة احتياطية فورية...")
            self.create_auto_backup()
            
            self.is_running = True
            
            # تشغيل المنظم في خيط منفصل
            def run_scheduler():
                while self.is_running:
                    schedule.run_pending()
                    time.sleep(60)  # فحص كل دقيقة
            
            self.thread = threading.Thread(target=run_scheduler, daemon=True)
            self.thread.start()
            
            self.logger.info("✅ تم بدء منظم النسخ الاحتياطي التلقائي بنجاح!")
            
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
            "thread_alive": self.thread.is_alive() if self.thread else False
        }

# متغير عام للمنظم
auto_backup_scheduler = None

def start_auto_backup(interval_minutes=None):
    """بدء النسخ الاحتياطي التلقائي"""
    # استخدام الإعداد من config أو القيمة الافتراضية 15 دقيقة
    if interval_minutes is None:
        interval_minutes = getattr(config, 'BACKUP_INTERVAL_MINUTES', 15)
    """بدء النسخ الاحتياطي التلقائي"""
    global auto_backup_scheduler
    
    if auto_backup_scheduler is None:
        auto_backup_scheduler = AutoBackupScheduler(interval_minutes)
    
    auto_backup_scheduler.start_scheduler()
    return auto_backup_scheduler

def stop_auto_backup():
    """إيقاف النسخ الاحتياطي التلقائي"""
    global auto_backup_scheduler
    
    if auto_backup_scheduler:
        auto_backup_scheduler.stop_scheduler()
        auto_backup_scheduler = None

def get_auto_backup_status():
    """الحصول على حالة النسخ الاحتياطي التلقائي"""
    global auto_backup_scheduler
    
    if auto_backup_scheduler:
        return auto_backup_scheduler.get_backup_status()
    else:
        return {
            "is_running": False,
            "interval_minutes": 0,
            "next_backup": "غير محدد",
            "thread_alive": False
        }































