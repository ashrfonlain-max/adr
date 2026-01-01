"""
خدمة إرسال تذكيرات الديون الأسبوعية
"""

import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any
import webbrowser
import urllib.parse

class DebtReminderService:
    """خدمة إرسال تذكيرات الديون"""
    
    def __init__(self, maintenance_service):
        self.maintenance_service = maintenance_service
        self.is_running = False
        self.thread = None
    
    def send_reminder_to_customer(self, customer_name: str, phone: str, amount: float, tracking_code: str) -> bool:
        """إرسال تذكير لعميل واحد"""
        try:
            # إنشاء رسالة التذكير
            message = f"""مرحباً {customer_name}،

🔔 تذكير ودي من ADR ELECTRONICS

لديك دين غير مسدد بمبلغ: {amount:.2f} $
رقم الطلب: {tracking_code}

نرجو منكم التكرم بالسداد في أقرب وقت ممكن.

شكراً لتعاملكم معنا 🙏

للاستفسار: اتصل بنا
ADR ELECTRONICS"""
            
            print(f"📱 تذكير للعميل {customer_name}: {message}")
            return True
        except Exception as e:
            print(f"خطأ في إرسال التذكير: {str(e)}")
            return False
    
    def send_weekly_reminders(self):
        """إرسال تذكيرات أسبوعية لجميع المدينين"""
        try:
            print(f"\n🔔 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] جاري إرسال تذكيرات الديون الأسبوعية...")
            
            # جلب قائمة الديون
            success, message, debts = self.maintenance_service.get_unpaid_jobs()
            
            if not success:
                print(f"❌ فشل في جلب قائمة الديون: {message}")
                return
            
            if not debts:
                print("✅ لا توجد ديون للتذكير بها")
                return
            
            print(f"📋 عدد المدينين: {len(debts)}")
            
            # إرسال تذكير لكل مدين
            sent_count = 0
            for debt in debts:
                # إرسال التذكير فقط للديون الأقدم من 3 أيام
                if debt['days_overdue'] >= 3:
                    success = self.send_reminder_to_customer(
                        customer_name=debt['customer_name'],
                        phone=debt['customer_phone'],
                        amount=debt['final_cost'],
                        tracking_code=debt['tracking_code']
                    )
                    
                    if success:
                        sent_count += 1
                        # انتظار قليلاً بين كل رسالة (لتجنب الإزعاج)
                        time.sleep(2)
            
            print(f"✅ تم إرسال {sent_count} تذكير من أصل {len(debts)} دين")
            
        except Exception as e:
            print(f"❌ خطأ في إرسال التذكيرات الأسبوعية: {str(e)}")
    
    def schedule_weekly_reminders(self):
        """جدولة التذكيرات الأسبوعية"""
        # إرسال التذكيرات كل يوم أحد الساعة 10:00 صباحاً
        schedule.every().sunday.at("10:00").do(self.send_weekly_reminders)
        
        # للاختبار: يمكن إرسال التذكيرات كل ساعة
        # schedule.every().hour.do(self.send_weekly_reminders)
        
        print("✅ تم جدولة التذكيرات الأسبوعية (كل يوم أحد الساعة 10:00 صباحاً)")
    
    def run_scheduler(self):
        """تشغيل المجدول"""
        self.is_running = True
        print("🔄 بدء خدمة التذكيرات الأسبوعية...")
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # فحص كل دقيقة
    
    def start(self):
        """بدء خدمة التذكيرات في خيط منفصل"""
        if self.thread is None or not self.thread.is_alive():
            self.schedule_weekly_reminders()
            self.thread = threading.Thread(target=self.run_scheduler, daemon=True)
            self.thread.start()
            print("✅ خدمة التذكيرات الأسبوعية تعمل في الخلفية")
    
    def stop(self):
        """إيقاف خدمة التذكيرات"""
        self.is_running = False
        print("⏹️ تم إيقاف خدمة التذكيرات الأسبوعية")
    
    def send_test_reminder(self):
        """إرسال تذكير تجريبي فوراً (للاختبار)"""
        print("🧪 إرسال تذكير تجريبي...")
        self.send_weekly_reminders()


