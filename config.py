"""
إعدادات التطبيق
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# إعدادات قاعدة البيانات
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "adr_maintenance")
DATABASE_URL = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'adr_maintenance.db')}"

# إعدادات التطبيق
APP_NAME = "نظام إدارة الصيانة"
VERSION = "1.0.0"
THEME = "light"  # light, dark, system

# مسارات الملفات
BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
REPORTS_FOLDER = os.path.join(BASE_DIR, "reports")
TEMP_FOLDER = os.path.join(BASE_DIR, "temp")

# إنشاء المجلدات إذا لم تكن موجودة
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORTS_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

# إعدادات العملة - الدولار أولوية
DEFAULT_CURRENCY = "USD"  # العملة الافتراضية (الدولار أولوية)
EXCHANGE_RATE = 90000.0  # سعر الصرف (1 دولار = 90000 ليرة لبنانية)
CURRENCY_SYMBOL = {
    "LBP": "ل.ل",
    "USD": "$"
}

# إعدادات الواجهة
ENABLE_MONTHLY_STATS = True  # تفعيل إحصائيات الشهر

# إعدادات رسائل الواتساب
DEFAULT_WHATSAPP_TEMPLATE = """🔧 تحديث حالة طلب الصيانة
رقم التتبع: {tracking_code}
الجهاز: {device_type}
الرقم التسلسلي: {serial_number}
الحالة الجديدة: {status}
{price_info}
تاريخ التحديث: {date}
شكراً لثقتكم بنا! 🙏"""

# قوالب رسائل الواتساب المخصصة
WHATSAPP_RECEIVED_MESSAGE = """🔧 ADR ELECTRONICS

تم استلام جهازكم رقم {tracking_code} بنجاح!

نوع الجهاز: {device_type}
الرقم التسلسلي: {serial_number}

سيتم إصلاحه في أقرب وقت ممكن.

شكراً لثقتكم بنا! 🙏"""

WHATSAPP_REPAIRED_MESSAGE = """مرحبا
تم الانتهاء من صيانة جهازكم

رقم التتبع: {tracking_code}
نوع الجهاز: {device_type}
الرقم التسلسلي: {serial_number}
{price_info}

يمكنكم الاستلام من مركزنا من الساعة 8 صباحاً إلى الساعة 6 مساءً

شكراً لثقتكم بنا 🙏"""

WHATSAPP_DELIVERED_MESSAGE = """✅ ADR ELECTRONICS

تم تسليم الجهاز رقم {tracking_code} بنجاح! 🎉

نوع الجهاز: {device_type}
الرقم التسلسلي: {serial_number}
{cost_info}
{payment_info}

نشكركم لثقتكم بنا ونتمنى لكم تجربة ممتازة!

شكراً لثقتكم بنا! 🙏"""

# إعدادات البريد الإلكتروني
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")

# إعدادات الإشعارات
NOTIFICATION_SETTINGS = {
    "email_enabled": True,
    "sms_enabled": False
}

# إعدادات النسخ الاحتياطي
BACKUP_TO_EXTERNAL_DRIVE = os.getenv("BACKUP_TO_EXTERNAL_DRIVE", "False").lower() == "true"
EXTERNAL_DRIVE_PATH = os.getenv("EXTERNAL_DRIVE_PATH", None)  # مثال: "D:\\" أو "/media/usb"

# إعدادات النسخ الاحتياطي التلقائي
BACKUP_INTERVAL_MINUTES = int(os.getenv("BACKUP_INTERVAL_MINUTES", "15"))  # كل 15 دقيقة افتراضياً (ربع ساعة)
BACKUP_TO_GOOGLE_DRIVE = os.getenv("BACKUP_TO_GOOGLE_DRIVE", "False").lower() == "true"

# إعدادات النسخ الاحتياطي التلقائي على USB
USB_BACKUP_INTERVAL_MINUTES = int(os.getenv("USB_BACKUP_INTERVAL_MINUTES", "10"))  # كل 10 دقائق افتراضياً
USB_DRIVE_PATH = os.getenv("USB_DRIVE_PATH", None)  # مسار USB محدد (اختياري - إذا لم يُحدد، سيتم الاكتشاف التلقائي)

# إعدادات كلمات المرور (يجب تعيينها في ملف .env)
DEBTS_PASSWORD = os.getenv("DEBTS_PASSWORD", "")  # كلمة مرور صفحة الديون
REPORTS_PASSWORD = os.getenv("REPORTS_PASSWORD", "")  # كلمة مرور صفحة التقارير
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")  # كلمة مرور المستخدم الافتراضي
REMOTE_ACCESS_PASSWORD = os.getenv("REMOTE_ACCESS_PASSWORD", "")  # كلمة مرور الوصول عن بُعد
