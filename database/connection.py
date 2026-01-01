"""
إعدادات اتصال قاعدة البيانات
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# إعدادات الاتصال بقاعدة البيانات
# دعم PostgreSQL للخوادم السحابية (Railway, Render, etc.)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # إصلاح رابط PostgreSQL (Railway يستخدم postgres:// بدلاً من postgresql://)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
elif os.getenv("DB_USER") and os.getenv("DB_PASSWORD"):
    # استخدام MySQL إذا كانت متغيرات البيئة موجودة
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "adr_maintenance")
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
else:
    # استخدام SQLite كبديل (للاستخدام المحلي)
    SQLALCHEMY_DATABASE_URL = "sqlite:///./adr_maintenance.db"

# إنشاء محرك قاعدة البيانات مع تحسينات الأداء
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    # تحسينات SQLite للأداء الأقصى
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30  # زيادة timeout
        },
        pool_pre_ping=True,
        pool_size=50,  # زيادة كبيرة لحجم الـ pool (من 20 إلى 50)
        max_overflow=100,  # زيادة كبيرة لـ max_overflow (من 40 إلى 100)
        echo=False,  # تعطيل SQL logging للأداء
        execution_options={
            "autocommit": False
        }
    )
    # تفعيل تحسينات SQLite المتقدمة (أسرع للقراءة المتعددة)
    # تطبيق الإعدادات على كل اتصال جديد تلقائياً
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_conn, connection_record):
        """تطبيق PRAGMA settings على كل اتصال جديد لضمان الأداء الأمثل"""
        try:
            cursor = dbapi_conn.cursor()
            # WAL mode - أسرع للقراءة المتعددة
            cursor.execute("PRAGMA journal_mode=WAL")
            # NORMAL sync - توازن بين السرعة والأمان
            cursor.execute("PRAGMA synchronous=NORMAL")
            # زيادة cache size بشكل كبير جداً (1GB)
            # القيمة السالبة تعني بالكيلوبايت، -1048576 = 1GB
            cursor.execute("PRAGMA cache_size=-1048576")  # 1GB cache (زيادة كبيرة)
            # تخزين مؤقت في الذاكرة
            cursor.execute("PRAGMA temp_store=MEMORY")
            # memory-mapped I/O - أسرع للقراءة (2GB)
            # 2147483648 bytes = 2GB
            cursor.execute("PRAGMA mmap_size=2147483648")  # 2GB (زيادة كبيرة)
            # تحسينات إضافية
            cursor.execute("PRAGMA page_size=4096")  # حجم صفحة أكبر
            # زيادة buffer size في الذاكرة
            cursor.execute("PRAGMA busy_timeout=30000")  # 30 ثانية timeout
            # استخدام أكبر عدد من الـ threads المتاحة
            cursor.execute("PRAGMA threads=16")  # استخدام 16 threads (زيادة كبيرة)
            # تحسينات القراءة
            cursor.execute("PRAGMA read_uncommitted=1")  # قراءة أسرع
            cursor.close()
        except Exception:
            # تجاهل الأخطاء في PRAGMA (قد لا تكون مدعومة في بعض الإصدارات)
            pass
elif "postgresql" in SQLALCHEMY_DATABASE_URL or "postgres" in SQLALCHEMY_DATABASE_URL:
    # تحسينات PostgreSQL (للخوادم السحابية)
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        poolclass=NullPool,  # NullPool للخوادم السحابية (Serverless)
        pool_pre_ping=True,
        echo=False,  # تعطيل SQL logging للأداء
        connect_args={
            "connect_timeout": 10,
            "sslmode": "require"  # SSL مطلوب للخوادم السحابية
        }
    )
else:
    # تحسينات MySQL
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=50,  # زيادة كبيرة
        max_overflow=100,  # زيادة كبيرة
        pool_recycle=3600,  # إعادة تدوير الاتصالات كل ساعة
        echo=False,  # تعطيل SQL logging للأداء
        connect_args={
            "connect_timeout": 10,
            "read_timeout": 10,
            "write_timeout": 10
        }
    )

# إنشاء جلسة قاعدة البيانات
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# القاعدة للتعريفات
Base = declarative_base()

def get_db():
    """
    الحصول على جلسة قاعدة بيانات
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    تهيئة قاعدة البيانات وإنشاء الجداول - محسّن لسرعة الفتح
    """
    import database.models
    # استخدام checkfirst=True لتجنب فحص الجداول إذا كانت موجودة (أسرع)
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception:
        # إذا فشل، استخدم الطريقة العادية
        Base.metadata.create_all(bind=engine)
