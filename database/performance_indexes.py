"""
إضافة فهارس متقدمة لتحسين الأداء بشكل خارق
"""

from sqlalchemy import text, Index
from database.connection import engine, Base
from database.models import MaintenanceJob, Customer, Payment

def create_performance_indexes():
    """إنشاء فهارس متقدمة لتحسين الأداء"""
    
    with engine.connect() as conn:
        try:
            # فهارس مركبة للبحث السريع
            # 1. فهرس مركب على (status, received_at) - للبحث حسب الحالة والتاريخ
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status_received 
                ON maintenance_jobs(status, received_at DESC)
            """))
            
            # 2. فهرس مركب على (customer_id, status) - لطلبات العميل
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_customer_status 
                ON maintenance_jobs(customer_id, status)
            """))
            
            # 3. فهرس مركب على (payment_status, status) - للديون
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_payment_status 
                ON maintenance_jobs(payment_status, status)
            """))
            
            # 4. فهرس مركب على (technician_id, status) - لطلبات الفني
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_technician_status 
                ON maintenance_jobs(technician_id, status)
            """))
            
            # 5. فهرس على (received_at DESC) - للترتيب حسب التاريخ
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_received_desc 
                ON maintenance_jobs(received_at DESC)
            """))
            
            # 6. فهرس على (created_at DESC) - للترتيب حسب الإنشاء
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_created_desc 
                ON maintenance_jobs(created_at DESC)
            """))
            
            # 7. فهرس مركب على (device_type, status) - للبحث حسب نوع الجهاز
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_device_status 
                ON maintenance_jobs(device_type, status)
            """))
            
            # 8. فهرس على (tracking_code) - للبحث السريع (موجود لكن نتأكد)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_tracking_code 
                ON maintenance_jobs(tracking_code)
            """))
            
            # فهارس للعملاء
            # 9. فهرس مركب على (name, phone) - للبحث السريع
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_customers_name_phone 
                ON customers(name, phone)
            """))
            
            # 10. فهرس على (created_at DESC) - للترتيب
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_customers_created_desc 
                ON customers(created_at DESC)
            """))
            
            conn.commit()
            print("✅ تم إنشاء جميع الفهارس المتقدمة بنجاح!")
            return True
            
        except Exception as e:
            print(f"⚠️ خطأ في إنشاء الفهارس: {e}")
            conn.rollback()
            return False

def optimize_sqlite_settings():
    """تحسين إعدادات SQLite بشكل متقدم"""
    
    with engine.connect() as conn:
        try:
            # تحسينات إضافية للأداء
            conn.execute(text("PRAGMA optimize"))  # تحسين تلقائي
            conn.execute(text("PRAGMA analysis_limit=1000"))  # تحليل أسرع
            conn.execute(text("PRAGMA automatic_index=ON"))  # فهارس تلقائية
            conn.execute(text("PRAGMA query_only=OFF"))  # تأكد من وضع الكتابة
            conn.commit()
            print("✅ تم تحسين إعدادات SQLite!")
            return True
        except Exception as e:
            print(f"⚠️ خطأ في تحسين SQLite: {e}")
            return False

if __name__ == "__main__":
    print("🚀 بدء إنشاء الفهارس المتقدمة...")
    create_performance_indexes()
    optimize_sqlite_settings()
    print("✅ اكتمل!")














