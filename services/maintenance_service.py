"""
خدمات إدارة الصيانة
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, and_, or_, exists, text
import random
import string
import re
import config
from config import WHATSAPP_RECEIVED_MESSAGE, WHATSAPP_REPAIRED_MESSAGE, WHATSAPP_DELIVERED_MESSAGE

from database.models import (
    MaintenanceJob, Customer, User, MaintenanceStatus,
    StatusHistory, UsedPart, Part, Payment, PaymentStatus, SystemSettings, JobExpense
)

# استيراد نظام Cache المتقدم
from utils.performance_cache import app_cache, cached
from utils.logger import service_logger as logger

class MaintenanceService:
    """خدمات إدارة الصيانة"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def convert_currency(self, amount: float, from_currency: str, to_currency: str) -> float:
        """تحويل العملة بين الدولار والليرة اللبنانية"""
        if from_currency == to_currency:
            return amount
        
        exchange_rate = config.EXCHANGE_RATE
        
        if from_currency == "USD" and to_currency == "LBP":
            # تحويل من دولار إلى ليرة
            return amount * exchange_rate
        elif from_currency == "LBP" and to_currency == "USD":
            # تحويل من ليرة إلى دولار
            return amount / exchange_rate
        else:
            return amount
    
    def format_currency(self, amount: float, currency: str = None) -> str:
        """تنسيق المبلغ مع رمز العملة"""
        if currency is None:
            currency = config.DEFAULT_CURRENCY
        
        symbol = config.CURRENCY_SYMBOL.get(currency, "")
        return f"{amount:,.2f} {symbol}"
    
    def generate_tracking_code(self, code_type: str = "A") -> str:
        """إنشاء رمز تتبع فريد حسب النوع المحدد - محسّن للأداء بشكل خارق
        
        ملاحظة: لا نستخدم Cache هنا لأن كل كود يجب أن يكون فريداً
        لكن الاستعلام محسّن جداً ليكون سريعاً بدون cache
        """
        # تحويل نوع الكود إلى أحرف كبيرة وإزالة المسافات للاتساق
        code_type = code_type.upper().strip()
        
        try:
            # استخدام استعلام SQL محسّن جداً - استخراج أكبر رقم مباشرة من قاعدة البيانات
            # هذا أسرع بكثير من جلب 100 كود ومعالجتها في Python
            sql_query = text("""
                SELECT MAX(CAST(
                    SUBSTR(
                        REPLACE(UPPER(TRIM(tracking_code)), ' ', ''),
                        LENGTH(:code_type) + 1
                    ) AS INTEGER
                )) as max_num
                FROM maintenance_jobs 
                WHERE UPPER(REPLACE(TRIM(tracking_code), ' ', '')) LIKE :pattern
                AND SUBSTR(REPLACE(UPPER(TRIM(tracking_code)), ' ', ''), 1, LENGTH(:code_type)) = :code_type
                AND SUBSTR(REPLACE(UPPER(TRIM(tracking_code)), ' ', ''), LENGTH(:code_type) + 1) GLOB '[0-9]*'
            """)
            
            result = self.db.execute(sql_query, {
                "pattern": f"{code_type}%",
                "code_type": code_type
            })
            row = result.fetchone()
            max_number = row[0] if row and row[0] is not None else 0
            
            # إرجاع الكود التالي
            new_number = max_number + 1
            return f"{code_type}{new_number}"
            
        except Exception as e:
            # في حالة حدوث أي خطأ، جرب الطريقة البديلة المحسّنة
            try:
                # طريقة بديلة محسّنة: استخدام ORM مع limit أصغر
                recent_codes = self.db.query(MaintenanceJob.tracking_code)\
                                     .filter(MaintenanceJob.tracking_code.ilike(f'{code_type}%'))\
                                     .order_by(MaintenanceJob.id.desc())\
                                     .limit(50)\
                                     .all()
                
                if not recent_codes:
                    return f"{code_type}1"
                
                max_number = 0
                import re
                
                for code_tuple in recent_codes:
                    code = code_tuple[0] if isinstance(code_tuple, tuple) else code_tuple
                    if code:
                        code_clean = str(code).replace(" ", "").upper().strip()
                        if code_clean.startswith(code_type):
                            try:
                                code_without_prefix = code_clean[len(code_type):].strip()
                                if code_without_prefix:
                                    match = re.search(r'^\d+', code_without_prefix)
                                    if match:
                                        number = int(match.group())
                                        if number > max_number:
                                            max_number = number
                            except:
                                continue
                
                return f"{code_type}{max_number + 1}"
            except:
                # في حالة فشل جميع المحاولات، ابدأ من 1
                return f"{code_type}1"
    
    def create_maintenance_job(
        self,
        customer_name: str,
        phone: str,
        device_type: str,
        issue_description: str,
        device_model: Optional[str] = None,
        serial_number: Optional[str] = None,
        estimated_cost: float = 0.0,
        estimated_cost_currency: str = "USD",
        notes: Optional[str] = None,
        status: str = "received",
        email: Optional[str] = None,
        address: Optional[str] = None,
        code_type: str = "A"
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """إنشاء طلب صيانة جديد"""
        try:
            # البحث عن العميل أو إنشاؤه (محسّن مع فهرس على name و phone)
            customer = self.db.query(Customer).filter(
                Customer.name == customer_name,
                Customer.phone == phone
            ).first()
            
            if not customer:
                # إنشاء عميل جديد
                customer = Customer(
                    name=customer_name,
                    phone=phone,
                    email=email,
                    address=address
                )
                self.db.add(customer)
                self.db.flush()  # للحصول على ID العميل
            
            # إنشاء رمز التتبع
            tracking_code = self.generate_tracking_code(code_type)
            
            # تحويل التكلفة إلى الدولار إذا كانت بالليرة اللبنانية
            if estimated_cost_currency == "LBP" and estimated_cost > 0:
                estimated_cost_usd = self.convert_currency(estimated_cost, "LBP", "USD")
            else:
                estimated_cost_usd = estimated_cost
            
            # إنشاء طلب الصيانة
            job = MaintenanceJob(
                tracking_code=tracking_code,
                customer_id=customer.id,
                device_type=device_type,
                device_model=device_model,
                serial_number=serial_number,
                issue_description=issue_description,
                status=status,
                estimated_cost=estimated_cost_usd,  # حفظ بالدولار دائماً
                estimated_cost_currency=estimated_cost_currency,  # العملة الأصلية
                notes=notes,
                received_at=datetime.utcnow(),
                payment_status="paid",  # الكاش هو الافتراضي دائماً
                payment_method="cash"  # طريقة الدفع الافتراضية
            )
            
            self.db.add(job)
            
            # تسجيل تغيير الحالة
            status_history = StatusHistory(
                maintenance_job=job,
                status=status,
                notes="تم استلام الجهاز"
            )
            self.db.add(status_history)
            
            self.db.commit()
            
            # إرجاع بيانات الطلب
            job_data = {
                'id': job.id,
                'tracking_code': job.tracking_code,
                'customer_name': customer.name,
                'device_type': job.device_type,
                'device_model': job.device_model,
                'serial_number': job.serial_number,
                'status': job.status,
                'received_at': job.received_at
            }
            
            return True, f"تم إنشاء طلب الصيانة برقم {tracking_code}", job_data
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء إنشاء طلب الصيانة: {str(e)}", None
    
    def update_customer(
        self,
        customer_id: int,
        name: str,
        phone: str,
        email: Optional[str] = None,
        address: Optional[str] = None
    ) -> Tuple[bool, str]:
        """تحديث بيانات العميل - محسّن"""
        try:
            # استخدام exists() للتحقق من وجود العميل (أسرع)
            if not self.db.query(exists().where(Customer.id == customer_id)).scalar():
                return False, "العميل غير موجود"
            
            # تحديث مباشر بدون جلب الكائن (أسرع للبيانات الكبيرة)
            self.db.query(Customer).filter(Customer.id == customer_id).update({
                "name": name,
                "phone": phone,
                "email": email,
                "address": address,
                "updated_at": datetime.utcnow()
            }, synchronize_session=False)
            
            self.db.commit()
            return True, "تم تحديث بيانات العميل بنجاح"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء تحديث بيانات العميل: {str(e)}"
    
    def update_maintenance_job(
        self,
        job_id: int,
        device_type: Optional[str] = None,
        device_model: Optional[str] = None,
        serial_number: Optional[str] = None,
        issue_description: Optional[str] = None,
        notes: Optional[str] = None,
        final_cost: Optional[float] = None,
        final_cost_currency: Optional[str] = None,
        tracking_code: Optional[str] = None
    ) -> Tuple[bool, str]:
        """تحديث بيانات طلب الصيانة - محسّن"""
        try:
            # استخدام exists() للتحقق من وجود الطلب (أسرع)
            if not self.db.query(exists().where(MaintenanceJob.id == job_id)).scalar():
                return False, "طلب الصيانة غير موجود"
            
            if tracking_code:
                # إزالة المسافات وتحويل إلى أحرف كبيرة للاتساق
                tracking_code = tracking_code.replace(" ", "").upper()
                
                # التحقق من عدم تكرار الكود (استخدام exists() - أسرع)
                if self.db.query(exists().where(
                    MaintenanceJob.tracking_code == tracking_code,
                    MaintenanceJob.id != job_id
                )).scalar():
                    return False, f"كود التتبع '{tracking_code}' مستخدم بالفعل"
            
            # بناء قاموس التحديث
            update_dict = {"updated_at": datetime.utcnow()}
            if device_type:
                update_dict["device_type"] = device_type
            if device_model:
                update_dict["device_model"] = device_model
            if serial_number:
                update_dict["serial_number"] = serial_number
            if issue_description:
                update_dict["issue_description"] = issue_description
            if notes:
                update_dict["notes"] = notes
            if final_cost is not None:
                update_dict["final_cost"] = final_cost
            if final_cost_currency:
                update_dict["final_cost_currency"] = final_cost_currency.upper()
            if tracking_code:
                update_dict["tracking_code"] = tracking_code
            
            # تحديث مباشر بدون جلب الكائن (أسرع)
            self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).update(
                update_dict, synchronize_session=False
            )
            
            self.db.commit()
            
            # مسح Cache بعد التحديث
            app_cache.invalidate_pattern("search_jobs")
            app_cache.invalidate_pattern("get_jobs")
            app_cache.invalidate_pattern("get_dashboard_stats")
            app_cache.invalidate_pattern("get_report_data")
            
            return True, "تم تحديث بيانات طلب الصيانة بنجاح"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء تحديث بيانات طلب الصيانة: {str(e)}"
    
    def get_last_used_tracking_code(self, code_type: str) -> str:
        """الحصول على آخر كود تم استخدامه فعلياً من نوع معين"""
        try:
            # تحويل نوع الكود إلى أحرف كبيرة للاتساق
            code_type = code_type.upper().strip()
            
            last_job = self.db.query(MaintenanceJob.tracking_code)\
                              .filter(MaintenanceJob.tracking_code.like(f'{code_type}%'))\
                              .order_by(MaintenanceJob.id.desc())\
                              .limit(1)\
                              .scalar()
            
            if not last_job:
                return f"{code_type}1"
            
            # إزالة المسافات والتحقق من صحة الكود
            last_job = last_job.replace(" ", "").upper()
            
            if last_job.startswith(code_type):
                return last_job
            else:
                return f"{code_type}1"
                
        except SQLAlchemyError:
            return f"{code_type.upper()}1"
    
    def generate_new_tracking_code(self, code_type: str) -> str:
        """توليد كود تتبع جديد حسب النوع المطلوب"""
        return self.generate_tracking_code(code_type)
    
    def get_available_tracking_codes(self, code_type: str) -> List[str]:
        """الحصول على قائمة بالأكواد المتاحة لنوع معين - محسّن"""
        try:
            # استخدام scalar بدلاً من first() لتحسين الأداء
            last_code = self.db.query(MaintenanceJob.tracking_code)\
                              .filter(MaintenanceJob.tracking_code.like(f'{code_type}%'))\
                              .order_by(MaintenanceJob.id.desc())\
                              .limit(1)\
                              .scalar()
            
            if not last_code:
                return [f"{code_type}1"]
            
            # استخراج الرقم من آخر كود
            if last_code.startswith(code_type):
                try:
                    number = int(last_code[1:])
                    # إرجاع الأكواد المتاحة (الآخر + 5 أكواد إضافية)
                    return [f"{code_type}{i}" for i in range(number + 1, number + 6)]
                except ValueError:
                    return [f"{code_type}1"]
            else:
                return [f"{code_type}1"]
                
        except SQLAlchemyError:
            return [f"{code_type}1"]
    
    def delete_job(self, job_id: int) -> Tuple[bool, str]:
        """حذف طلب صيانة - محسّن"""
        try:
            # استخدام exists() للتحقق من وجود الطلب (أسرع من first())
            if not self.db.query(exists().where(MaintenanceJob.id == job_id)).scalar():
                return False, "طلب الصيانة غير موجود"
            
            # حذف السجلات المرتبطة دفعة واحدة (أسرع)
            self.db.query(StatusHistory).filter_by(maintenance_job_id=job_id).delete(synchronize_session=False)
            self.db.query(UsedPart).filter_by(maintenance_job_id=job_id).delete(synchronize_session=False)
            self.db.query(Payment).filter_by(maintenance_job_id=job_id).delete(synchronize_session=False)
            
            # حذف طلب الصيانة
            self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).delete(synchronize_session=False)
            self.db.commit()
            
            return True, "تم حذف طلب الصيانة بنجاح"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء حذف طلب الصيانة: {str(e)}"
    
    def update_job_status(
        self,
        job_id: int,
        new_status: str,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """تحديث حالة طلب الصيانة - محسّن"""
        try:
            job = self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
            if not job:
                return False, "طلب الصيانة غير موجود"
            
            # التحقق من صحة الحالة الجديدة
            valid_statuses = [s.value for s in MaintenanceStatus]
            if new_status not in valid_statuses:
                return False, f"حالة غير صالحة. الحالات المتاحة: {', '.join(valid_statuses)}"
            
            old_status = job.status
            job.status = new_status
            
            # تحديث أوقات الحالة الخاصة
            now = datetime.utcnow()
            if new_status == "completed":
                job.completed_at = now
            elif new_status == "delivered":
                job.delivered_at = now
            
            # تسجيل تغيير الحالة
            status_history = StatusHistory(
                maintenance_job_id=job_id,
                status=new_status,
                notes=notes,
                changed_by_id=user_id
            )
            self.db.add(status_history)
            
            self.db.commit()
            
            # مسح Cache بعد التحديث
            app_cache.invalidate_pattern("search_jobs")
            app_cache.invalidate_pattern("get_jobs")
            app_cache.invalidate_pattern("get_dashboard_stats")
            app_cache.invalidate_pattern("get_unpaid_jobs")
            app_cache.invalidate_pattern("get_report_data")
            
            return True, f"تم تحديث حالة الطلب من '{old_status}' إلى '{new_status}'"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء تحديث حالة الطلب: {str(e)}"
    
    def batch_update_job_status(
        self,
        job_ids: List[int],
        new_status: str,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """تحديث حالة عدة طلبات دفعة واحدة - محسّن للأداء"""
        try:
            if not job_ids:
                return False, "لم يتم تحديد أي طلبات", 0
            
            # التحقق من صحة الحالة الجديدة
            valid_statuses = [s.value for s in MaintenanceStatus]
            if new_status not in valid_statuses:
                return False, f"حالة غير صالحة. الحالات المتاحة: {', '.join(valid_statuses)}", 0
            
            # تحديث جميع الطلبات في استعلام واحد (أسرع بكثير)
            now = datetime.utcnow()
            update_dict = {"status": new_status}
            
            if new_status == "completed":
                update_dict["completed_at"] = now
            elif new_status == "delivered":
                update_dict["delivered_at"] = now
            
            # تحديث الطلبات دفعة واحدة
            updated_count = self.db.query(MaintenanceJob)\
                .filter(MaintenanceJob.id.in_(job_ids))\
                .update(update_dict, synchronize_session=False)
            
            # إضافة سجلات تغيير الحالة
            status_histories = [
                StatusHistory(
                    maintenance_job_id=job_id,
                    status=new_status,
                    notes=notes,
                    changed_by_id=user_id
                )
                for job_id in job_ids
            ]
            self.db.bulk_save_objects(status_histories)
            
            self.db.commit()
            
            return True, f"تم تحديث {updated_count} طلب بنجاح", updated_count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء تحديث الطلبات: {str(e)}", 0
    
    def add_part_to_job(
        self,
        job_id: int,
        part_id: int,
        quantity: int,
        unit_price: float,
        notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """إضافة قطعة غيار إلى طلب الصيانة - محسّن"""
        try:
            # التحقق من وجود الطلب والقطعة
            job = self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
            if not job:
                return False, "طلب الصيانة غير موجود"
                
            part = self.db.query(Part).filter(Part.id == part_id).first()
            if not part:
                return False, "قطعة الغيار غير موجودة"
            
            # التحقق من توفر الكمية
            if part.quantity < quantity:
                return False, f"الكمية المتوفرة غير كافية. المتوفر: {part.quantity}"
            
            # إضافة قطعة الغيار إلى الطلب
            used_part = UsedPart(
                maintenance_job_id=job_id,
                part_id=part_id,
                quantity=quantity,
                unit_price=unit_price,
                notes=notes
            )
            
            # تحديث كمية القطعة المتوفرة
            part.quantity -= quantity
            
            self.db.add(used_part)
            self.db.commit()
            
            return True, "تمت إضافة قطعة الغيار بنجاح"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء إضافة قطعة الغيار: {str(e)}"
    
    def record_payment(
        self,
        job_id: int,
        amount: float,
        payment_method: str,
        notes: Optional[str] = None,
        status: str = "paid"
    ) -> Tuple[bool, str]:
        """تسجيل دفعة جديدة - محسّن"""
        try:
            # التحقق من وجود الطلب
            job = self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
            if not job:
                return False, "طلب الصيانة غير موجود"
            
            # التحقق من صحة حالة الدفع
            valid_statuses = [s.value for s in PaymentStatus]
            if status not in valid_statuses:
                return False, f"حالة دفع غير صالحة. الحالات المتاحة: {', '.join(valid_statuses)}"
            
            # تسجيل الدفعة
            payment = Payment(
                maintenance_job_id=job_id,
                amount=amount,
                payment_method=payment_method,
                status=status,
                notes=notes
            )
            
            self.db.add(payment)
            self.db.commit()
            
            # تحديث حالة الطلب إذا تم الدفع بالكامل
            self._update_job_payment_status(job_id)
            
            # مسح Cache بعد التحديث
            app_cache.invalidate_pattern("get_unpaid_jobs")
            app_cache.invalidate_pattern("get_dashboard_stats")
            app_cache.invalidate_pattern("get_report_data")
            
            return True, "تم تسجيل الدفعة بنجاح"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء تسجيل الدفعة: {str(e)}"
    
    def _update_job_payment_status(self, job_id: int) -> None:
        """تحديث حالة دفع الطلب - محسّن"""
        # استخدام استعلام محسّن لحساب إجمالي المدفوعات بدون جلب جميع البيانات
        from sqlalchemy import func
        total_paid = self.db.query(func.sum(Payment.amount))\
                           .filter(Payment.maintenance_job_id == job_id)\
                           .filter(Payment.status != "delivered")\
                           .scalar() or 0.0
        
        job = self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
        if not job:
            return
        
        # حساب إجمالي التكلفة (النهائية إذا كانت موجودة، وإلا التقديرية)
        total_cost = job.final_cost or job.estimated_cost or 0
        
        # تحديث حالة الدفع
        if total_paid >= total_cost and total_cost > 0:
            job.payment_status = "paid"
        elif total_paid > 0:
            job.payment_status = "partial"
        else:
            job.payment_status = "pending"
        
        self.db.commit()
    
    def get_job_by_tracking_code(self, tracking_code: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """الحصول على تفاصيل طلب الصيانة باستخدام رقم التتبع - للعملاء"""
        try:
            # تنظيف رقم التتبع
            tracking_code = tracking_code.strip().upper().replace(" ", "")
            
            # استخدام eager loading للعلاقات الأساسية فقط (أسرع للعملاء)
            job = self.db.query(MaintenanceJob)\
                        .options(
                            joinedload(MaintenanceJob.customer)
                        )\
                        .filter(MaintenanceJob.tracking_code == tracking_code)\
                        .first()
            
            if not job:
                return False, "لم يتم العثور على الجهاز بهذا الرقم", None
            
            # تجميع بيانات الجهاز للعميل
            device_data = {
                "id": job.id,
                "tracking_code": job.tracking_code,
                "customer_name": job.customer.name,
                "device_type": job.device_type or "غير محدد",
                "device_model": job.device_model or "غير محدد",
                "serial_number": job.serial_number or "غير محدد",
                "status": job.status,
                "received_at": job.received_at.isoformat() if job.received_at else None,
                "notes": job.notes,
                "estimated_cost": float(job.estimated_cost) if job.estimated_cost else None,
                "estimated_cost_currency": job.estimated_cost_currency or "USD",
                "final_cost": float(job.final_cost) if job.final_cost else None,
                "final_cost_currency": job.final_cost_currency or "USD",
                "issue_description": job.issue_description
            }
            
            return True, "تم جلب بيانات الجهاز بنجاح", device_data
            
        except SQLAlchemyError as e:
            return False, f"حدث خطأ أثناء جلب بيانات الجهاز: {str(e)}", None
    
    def get_job_details(self, job_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """الحصول على تفاصيل طلب الصيانة - محسّن للأداء"""
        try:
            # استخدام eager loading لجميع العلاقات لتجنب مشكلة N+1 queries
            job = self.db.query(MaintenanceJob)\
                        .options(
                            joinedload(MaintenanceJob.customer),
                            joinedload(MaintenanceJob.technician),
                            selectinload(MaintenanceJob.parts).joinedload(UsedPart.part),
                            selectinload(MaintenanceJob.payments),
                            selectinload(MaintenanceJob.expenses),
                            selectinload(MaintenanceJob.status_history).joinedload(StatusHistory.changed_by)
                        )\
                        .filter(MaintenanceJob.id == job_id)\
                        .first()
            if not job:
                return False, "طلب الصيانة غير موجود", None
            
            # حساب إجمالي المدفوعات (محسّن: البيانات محملة مسبقاً)
            total_paid = sum(
                p.amount for p in job.payments 
                if p.status != "delivered"
            )
            
            # حساب إجمالي التكلفة (النهائية إذا كانت موجودة، وإلا التقديرية)
            total_cost = job.final_cost or job.estimated_cost or 0
            remaining = max(0, total_cost - total_paid)
            
            # تجميع تفاصيل الطلب
            details = {
                "id": job.id,
                "tracking_code": job.tracking_code,
                "customer": {
                    "id": job.customer.id,
                    "name": job.customer.name,
                    "phone": job.customer.phone,
                    "email": job.customer.email,
                    "address": job.customer.address
                },
                "device": {
                    "type": job.device_type,
                    "model": job.device_model,
                    "serial_number": job.serial_number
                },
                "issue": job.issue_description,
                "status": job.status,
                "received_at": job.received_at,
                "completed_at": job.completed_at,
                "delivered_at": job.delivered_at,
                "cost": {
                    "estimated": job.estimated_cost,
                    "final": job.final_cost,
                    "total_paid": total_paid,
                    "remaining": remaining
                },
                "parts": [
                    {
                        "id": part.part.id,
                        "name": part.part.name,
                        "quantity": part.quantity,
                        "unit_price": part.unit_price,
                        "total": part.quantity * part.unit_price,
                        "notes": part.notes
                    }
                    for part in job.parts
                ],
                "payments": [
                    {
                        "id": payment.id,
                        "amount": payment.amount,
                        "method": payment.payment_method,
                        "status": payment.status,
                        "notes": payment.notes,
                        "created_at": payment.created_at
                    }
                    for payment in job.payments
                    if payment.status != "delivered"
                ],
                "expenses": [
                    {
                        "id": expense.id,
                        "description": expense.description,
                        "amount": expense.amount,
                        "category": expense.category,
                        "is_included": expense.is_included,
                        "created_at": expense.created_at
                    }
                    for expense in job.expenses
                ],
                "status_history": [
                    {
                        "id": history.id,
                        "status": history.status,
                        "changed_by": history.changed_by.full_name if history.changed_by else "النظام",
                        "notes": history.notes,
                        "created_at": history.created_at
                    }
                    for history in job.status_history
                ],
                "notes": job.notes
            }
            
            return True, "تم جلب تفاصيل الطلب بنجاح", details
            
        except SQLAlchemyError as e:
            return False, f"حدث خطأ أثناء جلب تفاصيل الطلب: {str(e)}", None
    
    def search_jobs(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        technician_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """بحث في طلبات الصيانة (محسّن للأداء مع Cache)"""
        # بناء مفتاح cache من المعاملات
        cache_key = f"search_jobs:{query}:{status}:{customer_id}:{technician_id}:{start_date}:{end_date}:{limit}:{offset}"
        
        # محاولة الحصول من cache
        cached_result = app_cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # بناء الاستعلام مع eager loading لتقليل استعلامات N+1 (محسّن للأداء بشكل خارق)
            # استخدام joinedload فقط (أسرع من selectinload للعلاقات الصغيرة)
            # تحسين: استخدام inner join بدلاً من outer join (أسرع)
            q = self.db.query(MaintenanceJob)\
                       .options(
                           joinedload(MaintenanceJob.customer),  # أسرع للعلاقة 1-to-1
                           joinedload(MaintenanceJob.technician)  # أسرع للعلاقة 1-to-1
                           # إزالة selectinload للـ payments لتسريع الاستعلام (يمكن جلبها لاحقاً إذا لزم)
                       )\
                       .join(Customer, MaintenanceJob.customer_id == Customer.id)  # inner join صريح (أسرع)
            
            # تطبيق عوامل التصفية
            if query:
                search = f"%{query}%"
                q = q.filter(
                    (MaintenanceJob.tracking_code.ilike(search)) |
                    (Customer.name.ilike(search)) |
                    (MaintenanceJob.device_type.ilike(search)) |
                    (MaintenanceJob.device_model.ilike(search)) |
                    (MaintenanceJob.serial_number.ilike(search))
                )
            
            if status:
                # تحويل string إلى MaintenanceStatus enum
                try:
                    # إذا كان status string، نحوله إلى enum
                    if isinstance(status, str):
                        status_enum = MaintenanceStatus(status)
                    else:
                        status_enum = status
                    q = q.filter(MaintenanceJob.status == status_enum)
                except (ValueError, TypeError) as e:
                    # إذا فشل التحويل، نتجاهل الفلترة
                    # حالة غير صالحة - نتجاهل الفلترة
                    pass
                
            if customer_id:
                q = q.filter(MaintenanceJob.customer_id == customer_id)
                
            if technician_id:
                q = q.filter(MaintenanceJob.technician_id == technician_id)
                
            if start_date:
                q = q.filter(MaintenanceJob.received_at >= start_date)
                
            if end_date:
                # نضيف يوم كامل لتشمل نهاية اليوم المحدد
                from datetime import timedelta
                end_date = end_date + timedelta(days=1)
                q = q.filter(MaintenanceJob.received_at < end_date)
            
            # تنفيذ الاستعلام مع الترحيل - محسّن للأداء
            # استخدام index على received_at للترتيب السريع
            jobs = q.order_by(MaintenanceJob.received_at.desc())\
                   .offset(offset)\
                   .limit(limit)\
                   .all()
            
            # تحسين: استخدام yield_per للبيانات الكبيرة (لكن limit=10000 كافٍ هنا)
            
            # تجميع النتائج (البيانات محملة مسبقاً، لا حاجة لاستعلامات إضافية)
            result = []
            for job in jobs:
                # حساب إجمالي المدفوعات - محسّن للأداء
                # استخدام حالة الدفع لحساب سريع بدون استعلامات إضافية
                total_paid = 0
                if job.payment_status == 'paid':
                    total_paid = job.final_cost or job.estimated_cost or 0
                elif job.payment_status == 'partial':
                    # إذا كانت الحالة جزئية، نحسب من payments (محملة مسبقاً)
                    total_paid = sum(p.amount for p in getattr(job, 'payments', []) if p.status != "delivered")
                
                # حساب إجمالي التكلفة
                total_cost = job.final_cost or job.estimated_cost or 0
                
                result.append({
                    "id": job.id,
                    "tracking_code": job.tracking_code,
                    "customer_name": job.customer.name,
                    "customer_phone": job.customer.phone,
                    "device_type": job.device_type,
                    "device_model": job.device_model,
                    "serial_number": job.serial_number,
                    "status": job.status,
                    "received_at": job.received_at,
                    "completed_at": job.completed_at,
                    "delivered_at": job.delivered_at,
                    "estimated_cost": job.estimated_cost,
                    "final_cost": job.final_cost,
                    "total_paid": total_paid,
                    "remaining": max(0, total_cost - total_paid),
                    "payment_status": job.payment_status,
                    "payment_method": job.payment_method,
                    "technician_name": job.technician.full_name if job.technician else None
                })
            
            result_tuple = (True, "تم العثور على النتائج", result)
            
            # حفظ في cache (TTL محسّن - زيادة من 10 إلى 20 ثانية)
            app_cache.set(cache_key, result_tuple, ttl=20)
            
            return result_tuple
            
        except SQLAlchemyError as e:
            return False, f"حدث خطأ أثناء البحث: {str(e)}", []
    
    @cached(ttl=30)  # Cache لمدة 30 ثانية
    def get_dashboard_stats(self) -> Tuple[bool, str, Dict[str, Any]]:
        """الحصول على إحصائيات لوحة التحكم - محسّن للأداء مع Cache"""
        try:
            # استخدام استعلام واحد مع GROUP BY للحصول على جميع الإحصائيات دفعة واحدة
            from sqlalchemy import case
            
            # استعلام واحد للحصول على إحصائيات الحالات
            status_counts = self.db.query(
                MaintenanceJob.status,
                func.count(MaintenanceJob.id).label('count')
            ).group_by(MaintenanceJob.status).all()
            
            # تحويل النتائج إلى قاموس - استخدام .value للحصول على القيمة الفعلية من Enum
            status_dict = {}
            for status, count in status_counts:
                # إذا كان status هو Enum، استخدم .value، وإلا استخدم str()
                if hasattr(status, 'value'):
                    status_key = status.value
                elif hasattr(status, 'name'):
                    status_key = status.name.lower()
                else:
                    status_key = str(status)
                status_dict[status_key] = count
            
            # استخراج القيم
            received_count = status_dict.get('received', 0)
            not_repaired_count = status_dict.get('not_repaired', 0)
            repaired_count = status_dict.get('repaired', 0)
            delivered_count = status_dict.get('delivered', 0)
            
            # حساب الإجماليات
            total_jobs = sum(status_dict.values())
            in_progress = received_count + not_repaired_count
            
            # إجمالي الإيرادات باستخدام استعلام منفصل محسّن
            total_revenue = self.db.query(
                func.sum(MaintenanceJob.final_cost)
            ).filter(
                MaintenanceJob.status == MaintenanceStatus.DELIVERED,
                MaintenanceJob.final_cost.isnot(None),
                MaintenanceJob.final_cost > 0
            ).scalar() or 0
            
            # الحصول على تاريخ آخر تسليم
            last_delivery_date = self.db.query(
                func.max(MaintenanceJob.delivered_at)
            ).filter(
                MaintenanceJob.status == MaintenanceStatus.DELIVERED,
                MaintenanceJob.delivered_at.isnot(None)
            ).scalar()
            
            # أحدث الطلبات مع eager loading
            recent_jobs = self.db.query(MaintenanceJob)\
                               .options(joinedload(MaintenanceJob.customer))\
                               .order_by(MaintenanceJob.received_at.desc())\
                               .limit(5)\
                               .all()
            
            recent_jobs_list = [{
                "id": job.id,
                "tracking_code": job.tracking_code,
                "customer_name": job.customer.name,
                "device_type": job.device_type,
                "status": job.status,
                "received_at": job.received_at
            } for job in recent_jobs]
            
            # التحقق من صحة الحسابات (بدون طباعة للسرعة)
            
            # إحصائيات الحالة المفصلة
            status_stats = {
                "received": received_count,
                "not_repaired": not_repaired_count,
                "repaired": repaired_count,
                "delivered": delivered_count
            }
            
            # تجميع النتائج
            stats = {
                "total_jobs": total_jobs,
                "in_progress": in_progress,
                "ready_for_delivery": repaired_count,
                "delivered": delivered_count,
                "total_revenue": float(total_revenue) if total_revenue else 0.0,
                "last_delivery_date": last_delivery_date,
                "status_stats": status_stats,
                "recent_jobs": recent_jobs_list
            }
            
            return True, "تم جلب الإحصائيات بنجاح", stats
            
        except SQLAlchemyError as e:
            import traceback
            traceback.print_exc()
            return False, f"حدث خطأ أثناء جلب الإحصائيات: {str(e)}", {}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"حدث خطأ غير متوقع أثناء جلب الإحصائيات: {str(e)}", {}
    
    def update_payment_status(
        self,
        job_id: int,
        payment_status: str,
        payment_method: Optional[str] = None
    ) -> Tuple[bool, str]:
        """تحديث حالة الدفع - محسّن"""
        try:
            job = self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
            if not job:
                return False, "طلب الصيانة غير موجود"
            
            # التحقق من صحة حالة الدفع
            valid_statuses = ["paid", "unpaid"]
            if payment_status not in valid_statuses:
                return False, f"حالة دفع غير صالحة. الحالات المتاحة: {', '.join(valid_statuses)}"
            
            # التحقق من طريقة الدفع إذا كانت الحالة مدفوع
            if payment_status == "paid":
                if not payment_method:
                    # إذا لم يتم تحديد طريقة دفع، الكاش هو الافتراضي
                    payment_method = "cash"
                
                valid_methods = ["cash", "wish_money"]
                if payment_method not in valid_methods:
                    return False, f"طريقة دفع غير صالحة. الطرق المتاحة: {', '.join(valid_methods)}"
            
            # تحديث حالة الدفع
            job.payment_status = payment_status
            
            if payment_status == "paid":
                job.payment_method = payment_method
                job.payment_date = datetime.utcnow()
            else:
                job.payment_method = None
                job.payment_date = None
            
            self.db.commit()
            
            return True, "تم تحديث حالة الدفع بنجاح"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء تحديث حالة الدفع: {str(e)}"
    
    @cached(ttl=60)  # Cache لمدة دقيقة لأن الديون لا تتغير كثيراً
    def get_unpaid_jobs(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """الحصول على قائمة الطلبات غير المدفوعة (الديون) - محسّن للأداء"""
        try:
            # استخدام eager loading لتقليل استعلامات N+1
            jobs = self.db.query(MaintenanceJob)\
                          .options(joinedload(MaintenanceJob.customer))\
                          .filter(MaintenanceJob.payment_status == "unpaid")\
                          .filter(MaintenanceJob.status == MaintenanceStatus.DELIVERED)\
                          .order_by(MaintenanceJob.delivered_at.desc())\
                          .all()
            
            unpaid_jobs = []
            for job in jobs:
                unpaid_jobs.append({
                    "id": job.id,
                    "tracking_code": job.tracking_code,
                    "customer_id": job.customer_id,
                    "customer_name": job.customer.name,
                    "customer_phone": job.customer.phone,
                    "device_type": job.device_type,
                    "device_model": job.device_model,
                    "final_cost": job.final_cost or 0.0,
                    "delivered_at": job.delivered_at,
                    "days_overdue": (datetime.utcnow() - job.delivered_at).days if job.delivered_at else 0
                })
            
            return True, "تم جلب قائمة الديون بنجاح", unpaid_jobs
            
        except SQLAlchemyError as e:
            return False, f"حدث خطأ أثناء جلب قائمة الديون: {str(e)}", []
    
    @cached(ttl=60)  # Cache لمدة دقيقة
    def get_pending_old_jobs(self, days_threshold: int = 30, status: Optional[str] = None) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """الحصول على قائمة الأجهزة القديمة المعلقة (لم تُصلح أو لم تُسلم بعد)
        
        Args:
            days_threshold: عدد الأيام (افتراضي: 30)
            status: الحالة المحددة ('received' أو 'repaired') أو None لجميع الحالات
        """
        try:
            from datetime import timedelta
            
            # حساب التاريخ الحد الأدنى (قبل X يوم)
            threshold_date = datetime.utcnow() - timedelta(days=days_threshold)
            
            # تحديد الحالات المطلوبة
            if status == "received":
                status_filter = [MaintenanceStatus.RECEIVED]
            elif status == "repaired":
                status_filter = [MaintenanceStatus.REPAIRED]
            else:
                # إذا لم يتم تحديد حالة، نعرض جميع الحالات المعلقة
                status_filter = [MaintenanceStatus.RECEIVED, MaintenanceStatus.REPAIRED]
            
            # استخدام eager loading لتقليل استعلامات N+1
            # للأجهزة "repaired"، نفحص أيضاً completed_at إذا كان موجوداً
            if status == "repaired":
                # فلترة الأجهزة "repaired" القديمة: إما received_at قديم أو completed_at قديم
                jobs = self.db.query(MaintenanceJob)\
                              .options(joinedload(MaintenanceJob.customer))\
                              .filter(
                                  MaintenanceJob.status == MaintenanceStatus.REPAIRED,
                                  # إما received_at قديم أو (completed_at موجود وقديم)
                                  or_(
                                      MaintenanceJob.received_at <= threshold_date,
                                      and_(
                                          MaintenanceJob.completed_at.isnot(None),
                                          MaintenanceJob.completed_at <= threshold_date
                                      )
                                  )
                              )\
                              .order_by(MaintenanceJob.received_at.asc())\
                              .all()
            else:
                # للأجهزة "received" أو جميع الحالات، نفحص received_at فقط
                jobs = self.db.query(MaintenanceJob)\
                              .options(joinedload(MaintenanceJob.customer))\
                              .filter(
                                  # الأجهزة التي لم تُسلم بعد (received أو repaired حسب المعامل)
                                  MaintenanceJob.status.in_(status_filter),
                                  # الأجهزة القديمة (أكثر من X يوم)
                                  MaintenanceJob.received_at <= threshold_date
                              )\
                              .order_by(MaintenanceJob.received_at.asc())\
                              .all()
            
            pending_jobs = []
            for job in jobs:
                # حساب عدد الأيام منذ الاستلام
                days_since_received = (datetime.utcnow() - job.received_at).days if job.received_at else 0
                
                # حساب عدد الأيام منذ الإصلاح (إذا كان repaired)
                days_since_repaired = None
                if job.status == MaintenanceStatus.REPAIRED and job.completed_at:
                    days_since_repaired = (datetime.utcnow() - job.completed_at).days
                
                # حساب إجمالي المدفوعات (مثل search_jobs)
                total_paid = 0
                if job.payment_status == 'paid':
                    total_paid = job.final_cost or job.estimated_cost or 0
                elif job.payment_status == 'partial':
                    # إذا كانت الحالة جزئية، نحسب من payments
                    total_paid = sum(p.amount for p in getattr(job, 'payments', []) if p.status != "delivered")
                
                # حساب إجمالي التكلفة
                total_cost = job.final_cost or job.estimated_cost or 0
                
                pending_jobs.append({
                    "id": job.id,
                    "tracking_code": job.tracking_code,
                    "customer_id": job.customer_id,
                    "customer_name": job.customer.name,
                    "customer_phone": job.customer.phone,
                    "device_type": job.device_type,
                    "device_model": job.device_model,
                    "serial_number": job.serial_number,
                    "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
                    "received_at": job.received_at,
                    "completed_at": job.completed_at,
                    "delivered_at": job.delivered_at,  # مهم لعرض التاريخ في الجدول
                    "days_since_received": days_since_received,
                    "days_since_repaired": days_since_repaired,
                    "estimated_cost": job.estimated_cost or 0.0,
                    "final_cost": job.final_cost or 0.0,
                    "total_paid": total_paid,
                    "remaining": max(0, total_cost - total_paid),
                    "payment_status": job.payment_status or "unpaid",  # مهم للعرض
                    "payment_method": job.payment_method or "",  # مهم للعرض
                    "issue_description": job.issue_description,
                    "notes": job.notes
                })
            
            status_label = "قيد المعالجة" if status == "received" else ("جاهزة للتسليم" if status == "repaired" else "معلقة")
            return True, f"تم جلب {len(pending_jobs)} جهاز {status_label} قديم", pending_jobs
            
        except SQLAlchemyError as e:
            return False, f"حدث خطأ أثناء جلب قائمة الأجهزة المعلقة: {str(e)}", []
    
    @cached(ttl=30)  # Cache لمدة 30 ثانية
    def get_payment_summary(self) -> Tuple[bool, str, Dict[str, Any]]:
        """الحصول على ملخص المدفوعات - محسّن باستخدام استعلام واحد مع Cache"""
        try:
            from sqlalchemy import func, case
            
            # استخدام استعلام واحد مع CASE للحصول على جميع الإحصائيات دفعة واحدة
            summary = self.db.query(
                func.sum(
                    case(
                        (MaintenanceJob.payment_status == "unpaid", MaintenanceJob.final_cost),
                        else_=0
                    )
                ).label('total_unpaid'),
                func.count(
                    case(
                        (MaintenanceJob.payment_status == "unpaid", MaintenanceJob.id),
                        else_=None
                    )
                ).label('unpaid_count'),
                func.sum(
                    case(
                        (
                            (MaintenanceJob.payment_status == "paid") & 
                            (MaintenanceJob.payment_method == "cash"),
                            MaintenanceJob.final_cost
                        ),
                        else_=0
                    )
                ).label('cash_total'),
                func.sum(
                    case(
                        (
                            (MaintenanceJob.payment_status == "paid") & 
                            (MaintenanceJob.payment_method == "wish_money"),
                            MaintenanceJob.final_cost
                        ),
                        else_=0
                    )
                ).label('wish_money_total'),
                func.count(
                    case(
                        (
                            (MaintenanceJob.payment_status == "paid") & 
                            (MaintenanceJob.payment_method == "cash"),
                            MaintenanceJob.id
                        ),
                        else_=None
                    )
                ).label('cash_count'),
                func.count(
                    case(
                        (
                            (MaintenanceJob.payment_status == "paid") & 
                            (MaintenanceJob.payment_method == "wish_money"),
                            MaintenanceJob.id
                        ),
                        else_=None
                    )
                ).label('wish_money_count')
            ).filter(
                MaintenanceJob.status == MaintenanceStatus.DELIVERED
            ).first()
            
            total_unpaid = summary.total_unpaid or 0.0
            unpaid_count = summary.unpaid_count or 0
            cash_total = summary.cash_total or 0.0
            wish_money_total = summary.wish_money_total or 0.0
            cash_count = summary.cash_count or 0
            wish_money_count = summary.wish_money_count or 0
            
            summary = {
                "total_unpaid": float(total_unpaid),
                "unpaid_count": unpaid_count,
                "cash_total": float(cash_total),
                "cash_count": cash_count,
                "wish_money_total": float(wish_money_total),
                "wish_money_count": wish_money_count,
                "total_paid": float(cash_total + wish_money_total),
                "total_paid_count": cash_count + wish_money_count
            }
            
            return True, "تم جلب ملخص المدفوعات بنجاح", summary
            
        except SQLAlchemyError as e:
            return False, f"حدث خطأ أثناء جلب ملخص المدفوعات: {str(e)}", {}
    
    def get_system_setting(self, key: str, default_value: str = "") -> str:
        """الحصول على إعداد من النظام"""
        try:
            setting = self.db.query(SystemSettings).filter_by(setting_key=key).first()
            return setting.setting_value if setting else default_value
        except SQLAlchemyError:
            return default_value
    
    def set_system_setting(self, key: str, value: str, description: str = "") -> Tuple[bool, str]:
        """تعيين إعداد في النظام"""
        try:
            setting = self.db.query(SystemSettings).filter_by(setting_key=key).first()
            
            if setting:
                setting.setting_value = value
                setting.description = description
                setting.updated_at = datetime.utcnow()
            else:
                setting = SystemSettings(
                    setting_key=key,
                    setting_value=value,
                    description=description
                )
                self.db.add(setting)
            
            self.db.commit()
            return True, "تم حفظ الإعداد بنجاح"
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return False, f"حدث خطأ أثناء حفظ الإعداد: {str(e)}"
    
    def generate_custom_whatsapp_message(self, job_id: int, status: str, price: str = "", price_currency: Optional[str] = None) -> str:
        """إنشاء رسالة واتساب مخصصة - محسّن"""
        try:
            # جلب فقط الحقول المطلوبة لتحسين الأداء
            job = self.db.query(
                MaintenanceJob.tracking_code,
                MaintenanceJob.device_type,
                MaintenanceJob.serial_number,
                MaintenanceJob.final_cost_currency,
                MaintenanceJob.estimated_cost_currency,
                MaintenanceJob.final_cost,
                MaintenanceJob.estimated_cost,
                MaintenanceJob.payment_status,
                MaintenanceJob.payment_method
            )\
                        .filter(MaintenanceJob.id == job_id)\
                        .first()
            if not job:
                return ""
            
            # الحصول على قالب الرسالة المخصص حسب الحالة
            if status == "repaired":
                message_template = self.get_system_setting(
                    "whatsapp_repaired_message",
                    WHATSAPP_REPAIRED_MESSAGE
                )
            elif status == "delivered":
                message_template = self.get_system_setting(
                    "whatsapp_delivered_message",
                    WHATSAPP_DELIVERED_MESSAGE
                )
                # التأكد من أن القالب يحتوي على {payment_info} و {cost_info}
                if "{payment_info}" not in message_template:
                    # إضافة {payment_info} بعد {cost_info} أو في نهاية القالب
                    if "{cost_info}" in message_template:
                        message_template = message_template.replace("{cost_info}", "{cost_info}\n{payment_info}")
                    else:
                        # إضافة قبل السطر الأخير
                        lines = message_template.split('\n')
                        if len(lines) > 1:
                            lines.insert(-1, "{payment_info}")
                            message_template = '\n'.join(lines)
                        else:
                            message_template += "\n{payment_info}"
                
                if "{cost_info}" not in message_template:
                    # إضافة {cost_info} بعد {serial_number} أو في مكان مناسب
                    if "{serial_number}" in message_template:
                        message_template = message_template.replace("{serial_number}", "{serial_number}\n{cost_info}")
                    else:
                        lines = message_template.split('\n')
                        if len(lines) > 1:
                            lines.insert(-1, "{cost_info}")
                            message_template = '\n'.join(lines)
                        else:
                            message_template += "\n{cost_info}"
            else:
                message_template = self.get_system_setting(
                    "whatsapp_message_template",
                    config.DEFAULT_WHATSAPP_TEMPLATE
                )
            
            # إذا كانت الحالة تم الاستلام، لا نرسل رسالة
            if status == 'received':
                return ""
            
            # ترجمة الحالة
            status_translations = {
                'received': 'تم الاستلام',
                'repaired': 'تمت الصيانة',
                'delivered': 'تم التسليم'
            }
            
            arabic_status = status_translations.get(status, status)
            
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

            # إعداد معلومات السعر بالعملة المحفوظة
            price_info = ""
            if price and status == 'repaired':
                detected_currency = (
                    price_currency
                    or job.final_cost_currency
                    or job.estimated_cost_currency
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
            
            # إعداد معلومات التكلفة وحالة الدفع لرسالة التسليم
            cost_info = ""
            payment_info = ""
            if status == 'delivered':
                # جلب التكلفة (النهائية أو التقديرية)
                cost_amount = job.final_cost or job.estimated_cost
                cost_currency = job.final_cost_currency or job.estimated_cost_currency or config.DEFAULT_CURRENCY
                
                if cost_amount and cost_amount > 0:
                    cost_info = f"التكلفة: {format_amount(cost_amount, cost_currency)}"
                
                # جلب حالة الدفع - إعادة جلب الكائن بالكامل من قاعدة البيانات
                try:
                    # إعادة جلب الطلب الكامل من قاعدة البيانات للتأكد من أحدث حالة الدفع
                    self.db.expire_all()  # إلغاء cache للجلسة
                    full_job = self.db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
                    
                    if full_job:
                        payment_status = full_job.payment_status
                        payment_method = full_job.payment_method
                    else:
                        payment_status = job.payment_status
                        payment_method = job.payment_method
                except Exception as e:
                    payment_status = job.payment_status
                    payment_method = job.payment_method
                
                # معالجة حالة الدفع - معالجة القيم الفارغة أو None
                if payment_status:
                    payment_status_str = str(payment_status).strip().lower()
                    
                    if payment_status_str == "paid":
                        if payment_method:
                            payment_method_str = str(payment_method).strip().lower()
                            if payment_method_str == "cash":
                                payment_info = "حالة الدفع: 💵 كاش"
                            elif payment_method_str == "wish_money":
                                payment_info = "حالة الدفع: 💳 Wish"
                            else:
                                payment_info = "حالة الدفع: مدفوع"
                        else:
                            # إذا كانت الحالة مدفوع ولكن طريقة الدفع غير محددة، افترض كاش
                            payment_info = "حالة الدفع: 💵 كاش"
                    elif payment_status_str == "unpaid":
                        payment_info = "حالة الدفع: 📝 دين"
                    else:
                        # إذا كانت الحالة غير معروفة، لا نعرض شيء
                        payment_info = ""
                else:
                    # إذا لم تكن هناك حالة دفع محددة، لا نعرض شيء
                    payment_info = ""
            
            # تنظيف القالب من حقول غير مدعومة لمنع أخطاء الفورمات
            message_template = message_template.replace("{customer_name}", "").replace("{device_model}", "")

            # ملء القالب بالبيانات (بدون اسم العميل والموديل)
            try:
                message = message_template.format(
                    tracking_code=job.tracking_code,
                    device_type=job.device_type,
                    serial_number=job.serial_number or "غير محدد",
                    status=arabic_status,
                    price_info=price_info,
                    cost_info=cost_info,
                    payment_info=payment_info,
                    date=datetime.now().strftime('%Y-%m-%d %H:%M')
                )
            except KeyError as e:
                # محاولة التنسيق بدون المتغيرات المفقودة
                message = message_template.format(
                    tracking_code=job.tracking_code,
                    device_type=job.device_type,
                    serial_number=job.serial_number or "غير محدد",
                    status=arabic_status,
                    price_info=price_info or "",
                    cost_info=cost_info or "",
                    payment_info=payment_info or "",
                    date=datetime.now().strftime('%Y-%m-%d %H:%M')
                )
            
            # إزالة الأسطر الفارغة الناتجة عن حقول فارغة - تحسين المنطق
            lines = message.split('\n')
            cleaned_lines = []
            prev_was_empty = False
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                # إضافة السطر إذا:
                # 1. يحتوي على نص
                # 2. أو هو سطر فارغ بين سطرين يحتويان على نص (سطر فارغ واحد مسموح)
                if line_stripped:
                    cleaned_lines.append(line)
                    prev_was_empty = False
                elif not prev_was_empty and i < len(lines) - 1 and lines[i + 1].strip():
                    # سطر فارغ واحد مسموح بين سطرين يحتويان على نص
                    cleaned_lines.append(line)
                    prev_was_empty = True
                else:
                    prev_was_empty = True
            
            message = '\n'.join(cleaned_lines)
            
            # إزالة الأسطر الفارغة المتتالية (أكثر من سطرين متتاليين)
            message = re.sub(r'\n{3,}', '\n\n', message)
            
            return message
            
        except Exception as e:
            logger.error(f"خطأ في إنشاء رسالة الواتساب المخصصة: {e}", exc_info=True)
            return ""
    
    @cached(ttl=120)  # Cache لمدة دقيقتين للتقارير لأنها لا تتغير كثيراً
    def get_report_data(
        self,
        report_type: str,  # 'daily', 'weekly', 'monthly', 'yearly', 'custom'
        code_type: Optional[str] = None,  # 'A', 'B', 'C', 'D', None for all
        status: Optional[str] = 'delivered',  # 'delivered' or None for all
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """الحصول على بيانات التقرير - محسّن للأداء مع Cache"""
        try:
            # تحديد نطاق التاريخ حسب نوع التقرير
            now = datetime.utcnow()
            if report_type == 'daily':
                # استخدام بداية اليوم (00:00:00) والوقت الحالي عند طلب التقرير
                start_date = datetime(now.year, now.month, now.day, 0, 0, 0)
                end_date = now + timedelta(seconds=1)  # الوقت الحالي + ثانية واحدة لضمان تضمين جميع المدخلات
            elif report_type == 'weekly':
                # الأسبوع الحالي (من الاثنين)
                days_since_monday = now.weekday()
                start_date = datetime(now.year, now.month, now.day) - timedelta(days=days_since_monday)
                start_date = datetime(start_date.year, start_date.month, start_date.day)
                end_date = start_date + timedelta(days=7)
            elif report_type == 'monthly':
                start_date = datetime(now.year, now.month, 1)
                if now.month == 12:
                    end_date = datetime(now.year + 1, 1, 1)
                else:
                    end_date = datetime(now.year, now.month + 1, 1)
            elif report_type == 'yearly':
                start_date = datetime(now.year, 1, 1)
                end_date = datetime(now.year + 1, 1, 1)
            elif report_type == 'custom':
                if not start_date or not end_date:
                    return False, "يجب تحديد تاريخ البداية والنهاية للتقرير المخصص", {}
                # التأكد من أن end_date يشمل اليوم كاملاً
                end_date = datetime(end_date.year, end_date.month, end_date.day) + timedelta(days=1)
            else:
                return False, f"نوع التقرير غير صحيح: {report_type}", {}
            
            # بناء الاستعلام مع eager loading للعميل فقط (ما نحتاجه)
            query = self.db.query(MaintenanceJob).options(joinedload(MaintenanceJob.customer))
            
            # تصفية حسب نوع الكود
            if code_type:
                query = query.filter(MaintenanceJob.tracking_code.like(f'{code_type}%'))
            
            # تصفية حسب الحالة
            if status == 'delivered':
                query = query.filter(MaintenanceJob.status == MaintenanceStatus.DELIVERED)
                # إذا كانت الحالة "delivered"، استخدم delivered_at للتصفية
                if start_date:
                    query = query.filter(MaintenanceJob.delivered_at >= start_date)
                if end_date:
                    query = query.filter(MaintenanceJob.delivered_at < end_date)
            else:
                # إذا كانت جميع الحالات، استخدم received_at للتصفية
                if start_date:
                    query = query.filter(MaintenanceJob.received_at >= start_date)
                if end_date:
                    query = query.filter(MaintenanceJob.received_at < end_date)
            
            # استخدام استعلامات SQL محسّنة لحساب الإحصائيات بدلاً من معالجة Python
            # بناء شروط الفلترة للاستخدام في الاستعلامات الفرعية
            # ملاحظة: لا يمكن استخدام query.whereclause مباشرة في if - يجب استخدام is not None
            base_filter = query.whereclause if hasattr(query, 'whereclause') and query.whereclause is not None else None
            
            # حساب الإحصائيات الأساسية باستخدام SQL aggregate functions
            total_jobs = query.count()
            
            # حساب إجمالي الإيرادات باستخدام SQL
            revenue_query = self.db.query(func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0)))
            if base_filter is not None:
                revenue_query = revenue_query.filter(base_filter)
            total_revenue_result = revenue_query.scalar() or 0.0
            
            # حساب الإحصائيات للحالات
            if status == 'delivered':
                delivered_count = total_jobs
                delivered_revenue = total_revenue_result
            else:
                delivered_query = self.db.query(MaintenanceJob).filter(MaintenanceJob.status == MaintenanceStatus.DELIVERED)
                if base_filter is not None:
                    delivered_query = delivered_query.filter(base_filter)
                delivered_count = delivered_query.count()
                delivered_revenue_query = self.db.query(func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0)))\
                                                  .filter(MaintenanceJob.status == MaintenanceStatus.DELIVERED)
                if base_filter is not None:
                    delivered_revenue_query = delivered_revenue_query.filter(base_filter)
                delivered_revenue = float(delivered_revenue_query.scalar() or 0.0)
            
            # حساب متوسط السعر
            avg_price = total_revenue_result / total_jobs if total_jobs > 0 else 0
            
            # جلب البيانات للتفاصيل (مع حدود للتقرير الكبير - محسّن)
            # استخدام eager loading للتقليل من استعلامات N+1
            jobs = query.options(
                joinedload(MaintenanceJob.customer),
                selectinload(MaintenanceJob.payments)
            ).order_by(MaintenanceJob.received_at.desc()).limit(10000).all()
            
            # أفضل عميل (حسب عدد الأجهزة والإيرادات) - محسّن
            customer_query = self.db.query(
                MaintenanceJob.customer_id,
                Customer.name,
                func.count(MaintenanceJob.id).label('count'),
                func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0)).label('revenue')
            ).join(Customer)
            if base_filter is not None:
                customer_query = customer_query.filter(base_filter)
            customer_stats = customer_query.group_by(MaintenanceJob.customer_id, Customer.name)\
                                           .order_by(func.count(MaintenanceJob.id).desc())\
                                           .first()
            
            best_customer_by_count = {'name': customer_stats.name, 'count': customer_stats.count} if customer_stats else None
            
            customer_revenue_query = self.db.query(
                MaintenanceJob.customer_id,
                Customer.name,
                func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0)).label('revenue')
            ).join(Customer)
            if base_filter is not None:
                customer_revenue_query = customer_revenue_query.filter(base_filter)
            customer_stats_revenue = customer_revenue_query.group_by(MaintenanceJob.customer_id, Customer.name)\
                                                          .order_by(func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0)).desc())\
                                                          .first()
            
            best_customer_by_revenue = {'name': customer_stats_revenue.name, 'revenue': float(customer_stats_revenue.revenue)} if customer_stats_revenue else None
            
            # إحصائيات حسب نوع الجهاز - محسّن باستخدام SQL
            device_query = self.db.query(
                MaintenanceJob.device_type,
                func.count(MaintenanceJob.id).label('count'),
                func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0)).label('revenue')
            )
            if base_filter is not None:
                device_query = device_query.filter(base_filter)
            device_stats = device_query.group_by(MaintenanceJob.device_type).all()
            
            device_type_stats = {stat.device_type or 'غير محدد': {'count': stat.count, 'revenue': float(stat.revenue or 0)} for stat in device_stats}
            
            # إحصائيات حسب طريقة الدفع - محسّن باستخدام SQL
            payment_query = self.db.query(
                MaintenanceJob.payment_status,
                MaintenanceJob.payment_method,
                func.sum(func.coalesce(MaintenanceJob.final_cost, MaintenanceJob.estimated_cost, 0)).label('total')
            )
            if base_filter is not None:
                payment_query = payment_query.filter(base_filter)
            payment_stats_query = payment_query.group_by(MaintenanceJob.payment_status, MaintenanceJob.payment_method).all()
            
            payment_stats = {'cash': 0, 'wish_money': 0, 'unpaid': 0}
            for stat in payment_stats_query:
                if stat.payment_status == 'paid':
                    if stat.payment_method == 'cash':
                        payment_stats['cash'] += float(stat.total or 0)
                    elif stat.payment_method == 'wish_money':
                        payment_stats['wish_money'] += float(stat.total or 0)
                else:
                    payment_stats['unpaid'] += float(stat.total or 0)
            
            total_revenue = float(total_revenue_result)
            
            # ملاحظة: best_customer_by_count و best_customer_by_revenue تم تعريفهما بالفعل أعلاه
            # (في السطور 1143 و 1156) باستخدام استعلامات SQL محسّنة
            
            # تحضير بيانات الطلبات للجدول
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    'id': job.id,
                    'tracking_code': job.tracking_code,
                    'customer_name': job.customer.name,
                    'customer_phone': job.customer.phone,
                    'device_type': job.device_type,
                    'status': job.status.value if hasattr(job.status, 'value') else str(job.status),
                    'final_cost': job.final_cost or job.estimated_cost or 0,
                    'payment_status': job.payment_status,
                    'payment_method': job.payment_method,
                    'received_at': job.received_at,
                    'delivered_at': job.delivered_at
                })
            
            # إحصائيات الفترة السابقة للمقارنة
            previous_period_stats = None
            if report_type in ['daily', 'weekly', 'monthly', 'yearly']:
                if report_type == 'daily':
                    prev_start = start_date - timedelta(days=1)
                    prev_end = start_date
                elif report_type == 'weekly':
                    prev_start = start_date - timedelta(days=7)
                    prev_end = start_date
                elif report_type == 'monthly':
                    if start_date.month == 1:
                        prev_start = datetime(start_date.year - 1, 12, 1)
                    else:
                        prev_start = datetime(start_date.year, start_date.month - 1, 1)
                    prev_end = start_date
                elif report_type == 'yearly':
                    prev_start = datetime(start_date.year - 1, 1, 1)
                    prev_end = start_date
                
                prev_query = self.db.query(MaintenanceJob)
                if code_type:
                    prev_query = prev_query.filter(MaintenanceJob.tracking_code.like(f'{code_type}%'))
                if status == 'delivered':
                    prev_query = prev_query.filter(MaintenanceJob.status == MaintenanceStatus.DELIVERED)
                prev_query = prev_query.filter(
                    MaintenanceJob.received_at >= prev_start,
                    MaintenanceJob.received_at < prev_end
                )
                prev_jobs = prev_query.all()
                prev_total = len(prev_jobs)
                prev_revenue = sum(job.final_cost or job.estimated_cost or 0 for job in prev_jobs if job.final_cost or job.estimated_cost)
                
                previous_period_stats = {
                    'total_jobs': prev_total,
                    'total_revenue': prev_revenue,
                    'period_label': self._get_period_label(report_type, prev_start)
                }
            
            result = {
                'report_type': report_type,
                'code_type': code_type or 'جميع الأنواع',
                'status': status or 'جميع الحالات',
                'start_date': start_date,
                'end_date': end_date - timedelta(days=1) if end_date else None,
                'total_jobs': total_jobs,
                'total_revenue': total_revenue,
                'delivered_count': delivered_count,
                'delivered_revenue': delivered_revenue,
                'avg_price': avg_price,
                'best_customer_by_count': best_customer_by_count,
                'best_customer_by_revenue': best_customer_by_revenue,
                'device_type_stats': device_type_stats,
                'payment_stats': payment_stats,
                'jobs': jobs_data,
                'previous_period_stats': previous_period_stats
            }
            
            return True, "تم جلب بيانات التقرير بنجاح", result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"حدث خطأ أثناء جلب بيانات التقرير: {str(e)}", {}
    
    def _get_period_label(self, report_type: str, date: datetime) -> str:
        """الحصول على تسمية الفترة"""
        if report_type == 'daily':
            return date.strftime('%Y-%m-%d')
        elif report_type == 'weekly':
            return f"أسبوع {date.strftime('%Y-%m-%d')}"
        elif report_type == 'monthly':
            months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                     'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
            return f"{months[date.month - 1]} {date.year}"
        elif report_type == 'yearly':
            return str(date.year)
        return str(date)
    
    def get_jobs_by_month_week(self, status: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None, week_start: Optional[datetime] = None, week_end: Optional[datetime] = None) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """جلب الطلبات حسب الشهر والأسبوع"""
        try:
            from calendar import monthrange
            
            # بناء الاستعلام
            q = self.db.query(MaintenanceJob)\
                       .options(
                           joinedload(MaintenanceJob.customer),
                           joinedload(MaintenanceJob.technician)
                       )\
                       .join(Customer)
            
            # تطبيق فلتر الحالة
            if status:
                try:
                    if isinstance(status, str):
                        status_enum = MaintenanceStatus(status)
                    else:
                        status_enum = status
                    q = q.filter(MaintenanceJob.status == status_enum)
                    logger.debug(f"🔍 فلترة حسب الحالة: {status} -> {status_enum}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ خطأ في تحويل الحالة: {status} -> {e}")
                    pass
            
            # فلترة حسب الأسبوع إذا تم تحديده - فلترة دقيقة قبل تحديد date_field
            if week_start and week_end:
                # تحويل week_start و week_end إلى datetime إذا كانت date objects
                from datetime import date as date_type
                
                if isinstance(week_start, datetime):
                    week_start_dt = week_start
                elif isinstance(week_start, date_type):  # date object
                    week_start_dt = datetime.combine(week_start, datetime.min.time())
                else:
                    week_start_dt = week_start
                
                if isinstance(week_end, datetime):
                    # نهاية اليوم (23:59:59) لتشمل جميع الطلبات في اليوم الأخير
                    if week_end.hour == 0 and week_end.minute == 0 and week_end.second == 0:
                        week_end_dt = datetime.combine(week_end.date(), datetime.max.time())
                    else:
                        week_end_dt = week_end
                elif isinstance(week_end, date_type):  # date object
                    week_end_dt = datetime.combine(week_end, datetime.max.time())
                else:
                    week_end_dt = week_end
                
                # تحديد التاريخ المناسب حسب الحالة للفلترة الدقيقة
                # استخدام DATE() في SQLite للفلترة الدقيقة (مقارنة التواريخ فقط بدون الوقت)
                from sqlalchemy import func as sql_func, or_, cast, String
                from datetime import date as date_type
                
                # تحويل week_start_dt و week_end_dt إلى date objects للمقارنة
                if isinstance(week_start_dt, datetime):
                    week_start_date = week_start_dt.date()
                elif isinstance(week_start_dt, date_type):
                    week_start_date = week_start_dt
                else:
                    week_start_date = week_start_dt
                
                if isinstance(week_end_dt, datetime):
                    week_end_date = week_end_dt.date()
                elif isinstance(week_end_dt, date_type):
                    week_end_date = week_end_dt
                else:
                    week_end_date = week_end_dt
                
                # استخدام الفلترة المباشرة مع datetime objects
                # SQLite سيقارن التواريخ بشكل صحيح حتى مع وجود الوقت
                # لكن للتأكد من الدقة، نستخدم >= و <= مع week_start_dt و week_end_dt
                if status == "delivered":
                    # تم التسليم: استخدام delivered_at
                    # فلترة دقيقة: >= week_start_dt و <= week_end_dt
                    q = q.filter(
                        and_(
                            MaintenanceJob.delivered_at.isnot(None),
                            MaintenanceJob.delivered_at >= week_start_dt,
                            MaintenanceJob.delivered_at <= week_end_dt
                        )
                    )
                    date_field = MaintenanceJob.delivered_at
                elif status == "repaired":
                    # جاهز للتسليم: استخدام completed_at إذا كان موجوداً، وإلا received_at
                    # فلترة دقيقة: إما completed_at أو received_at يقع ضمن الأسبوع
                    q = q.filter(
                        or_(
                            and_(
                                MaintenanceJob.completed_at.isnot(None),
                                MaintenanceJob.completed_at >= week_start_dt,
                                MaintenanceJob.completed_at <= week_end_dt
                            ),
                            and_(
                                MaintenanceJob.completed_at.is_(None),
                                MaintenanceJob.received_at >= week_start_dt,
                                MaintenanceJob.received_at <= week_end_dt
                            )
                        )
                    )
                    date_field = sql_func.coalesce(MaintenanceJob.completed_at, MaintenanceJob.received_at)
                elif status == "received":
                    # قيد المعالجة: استخدام received_at
                    q = q.filter(
                        and_(
                            MaintenanceJob.received_at >= week_start_dt,
                            MaintenanceJob.received_at <= week_end_dt
                        )
                    )
                    date_field = MaintenanceJob.received_at
                else:
                    # إجمالي الطلبات: استخدام received_at
                    q = q.filter(
                        and_(
                            MaintenanceJob.received_at >= week_start_dt,
                            MaintenanceJob.received_at <= week_end_dt
                        )
                    )
                    date_field = MaintenanceJob.received_at
                
                logger.debug(f"🔍 فلترة الأسبوع الدقيقة: {week_start_date} إلى {week_end_date} للحالة: {status}")
                logger.debug(f"   ✅ استخدام datetime للفلترة الدقيقة: {week_start_dt} إلى {week_end_dt}")
                logger.debug(f"   📝 الاستعلام يفلتر حسب: {date_field}")
            else:
                # تحديد التاريخ المناسب حسب الحالة (للاستخدام في الترتيب فقط)
                if status == "delivered":
                    # تم التسليم: استخدام delivered_at
                    date_field = MaintenanceJob.delivered_at
                    # فلترة فقط الطلبات التي تم تسليمها
                    q = q.filter(MaintenanceJob.delivered_at.isnot(None))
                elif status == "repaired":
                    # جاهز للتسليم: استخدام completed_at إذا كان موجوداً، وإلا received_at
                    # استخدام coalesce للحصول على أول قيمة غير null
                    from sqlalchemy import func as sql_func
                    date_field = sql_func.coalesce(MaintenanceJob.completed_at, MaintenanceJob.received_at)
                elif status == "received":
                    # قيد المعالجة: استخدام received_at
                    date_field = MaintenanceJob.received_at
                else:
                    # إجمالي الطلبات: استخدام received_at
                    date_field = MaintenanceJob.received_at
                
                # فلترة حسب الشهر إذا تم تحديده (ولم يتم تحديد الأسبوع)
                if year and month:
                    # فلترة حسب الشهر
                    # الحصول على أول وآخر يوم في الشهر
                    first_day = datetime(year, month, 1)
                    last_day_num = monthrange(year, month)[1]
                    last_day = datetime(year, month, last_day_num, 23, 59, 59)
                    q = q.filter(and_(date_field >= first_day, date_field <= last_day))
                elif year:
                    # فلترة حسب السنة
                    first_day = datetime(year, 1, 1)
                    last_day = datetime(year, 12, 31, 23, 59, 59)
                    q = q.filter(and_(date_field >= first_day, date_field <= last_day))
            # إذا لم يتم تحديد أي فلترة تاريخية، نجلب جميع الطلبات للحالة المحددة
            
            # تحسين: استخدام eager loading للـ payments لتجنب N+1 queries
            q = q.options(selectinload(MaintenanceJob.payments))
            
            # تنفيذ الاستعلام مع الترتيب
            # إذا كان date_field هو coalesce، نستخدمه مباشرة، وإلا نستخدم nullslast
            if status == "repaired":
                # استخدام coalesce للترتيب
                jobs = q.order_by(date_field.desc()).all()
            else:
                # استخدام nullslast للتأكد من أن الطلبات بدون تاريخ تظهر في النهاية
                from sqlalchemy import nullslast
                jobs = q.order_by(nullslast(date_field.desc())).all()
            
            logger.debug(f"📊 عدد الطلبات المسترجعة: {len(jobs)}")
            if len(jobs) > 0:
                logger.debug(f"   أول طلب: {jobs[0].tracking_code if hasattr(jobs[0], 'tracking_code') else 'N/A'}")
                if week_start and week_end:
                    # التحقق من أن الطلبات المسترجعة ضمن النطاق المحدد
                    if status == "delivered" and jobs[0].delivered_at:
                        logger.debug(f"   ✅ تاريخ أول طلب: {jobs[0].delivered_at} (يجب أن يكون بين {week_start_dt} و {week_end_dt})")
                    elif status == "repaired":
                        job_date = jobs[0].completed_at if jobs[0].completed_at else jobs[0].received_at
                        logger.debug(f"   ✅ تاريخ أول طلب: {job_date} (يجب أن يكون بين {week_start_dt} و {week_end_dt})")
                    elif status == "received" and jobs[0].received_at:
                        logger.debug(f"   ✅ تاريخ أول طلب: {jobs[0].received_at} (يجب أن يكون بين {week_start_dt} و {week_end_dt})")
            
            # تجميع النتائج - محسّن: استخدام البيانات المحملة مسبقاً
            result = []
            for job in jobs:
                # تحديد التاريخ المناسب
                if status == "delivered" and job.delivered_at:
                    job_date = job.delivered_at
                elif status == "repaired":
                    # استخدام completed_at إذا كان موجوداً، وإلا received_at
                    job_date = job.completed_at if job.completed_at else job.received_at
                else:
                    job_date = job.received_at
                
                # حساب إجمالي المدفوعات - محسّن: استخدام payments المحملة مسبقاً
                total_paid = 0
                if job.payment_status == 'paid':
                    total_paid = job.final_cost or job.estimated_cost or 0
                elif job.payment_status == 'partial':
                    # استخدام payments المحملة مسبقاً بدلاً من getattr
                    total_paid = sum(p.amount for p in job.payments if p.status != "delivered")
                
                total_cost = job.final_cost or job.estimated_cost or 0
                
                result.append({
                    "id": job.id,
                    "tracking_code": job.tracking_code,
                    "customer_name": job.customer.name,
                    "customer_phone": job.customer.phone,
                    "device_type": job.device_type,
                    "device_model": job.device_model,
                    "serial_number": job.serial_number,
                    "status": job.status,
                    "received_at": job.received_at,
                    "completed_at": job.completed_at,
                    "delivered_at": job.delivered_at,
                    "job_date": job_date,  # التاريخ المناسب حسب الحالة
                    "estimated_cost": job.estimated_cost,
                    "final_cost": job.final_cost,
                    "total_paid": total_paid,
                    "remaining": max(0, total_cost - total_paid),
                    "payment_status": job.payment_status,
                    "issue_description": job.issue_description,
                    "notes": job.notes
                })
            
            return True, "تم جلب الطلبات بنجاح", result
            
        except Exception as e:
            return False, f"حدث خطأ أثناء جلب الطلبات: {str(e)}", []

