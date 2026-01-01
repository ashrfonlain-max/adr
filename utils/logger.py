"""
نظام التسجيل الاحترافي للنظام
يستبدل استخدام print() بنظام تسجيل منظم
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# إنشاء مجلد السجلات
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# مستويات التسجيل
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

def setup_logger(
    name: str = "maintenance_system",
    log_file: Optional[str] = None,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    إعداد نظام التسجيل الاحترافي
    
    Args:
        name: اسم الـ logger
        log_file: اسم ملف السجل (اختياري)
        level: مستوى التسجيل (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: الحد الأقصى لحجم ملف السجل (افتراضي: 10 MB)
        backup_count: عدد ملفات السجل الاحتياطية (افتراضي: 5)
    
    Returns:
        Logger: كائن Logger جاهز للاستخدام
    """
    logger = logging.getLogger(name)
    
    # تجنب إضافة معالجات متعددة لنفس الـ logger
    if logger.handlers:
        return logger
    
    # تعيين مستوى التسجيل
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # ملف السجل
    if not log_file:
        log_file = LOG_DIR / "app.log"
    else:
        log_file = LOG_DIR / log_file
    
    # معالج الملف (مع تدوير الملفات)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # حفظ كل شيء في الملف
    
    # معالج وحدة التحكم
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)  # عرض حسب المستوى المحدد
    
    # تنسيق الرسائل
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# إنشاء logger عام للنظام
logger = setup_logger("maintenance_system", level="INFO")

# إنشاء loggers متخصصة
gui_logger = setup_logger("maintenance_system.gui", "gui.log", level="INFO")
service_logger = setup_logger("maintenance_system.service", "service.log", level="INFO")
db_logger = setup_logger("maintenance_system.database", "database.log", level="WARNING")

def get_logger(module_name: str = None) -> logging.Logger:
    """
    الحصول على logger مخصص لوحدة معينة
    
    Args:
        module_name: اسم الوحدة (مثل 'gui.maintenance_window')
    
    Returns:
        Logger: كائن Logger مخصص
    """
    if module_name:
        return setup_logger(f"maintenance_system.{module_name}", level="INFO")
    return logger






