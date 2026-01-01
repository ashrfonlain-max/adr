"""
نماذج قاعدة البيانات
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from .connection import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TECHNICIAN = "technician"
    RECEPTIONIST = "receptionist"
    OPERATOR = "operator"

class User(Base):
    """نموذج المستخدمين"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RECEPTIONIST, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
    
    # العلاقات
    maintenance_jobs = relationship("MaintenanceJob", back_populates="technician")

class Customer(Base):
    """نموذج العملاء"""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    phone = Column(String(20), nullable=False, index=True)
    email = Column(String(100), index=True)
    address = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    maintenance_jobs = relationship("MaintenanceJob", back_populates="customer")

class MaintenanceStatus(str, enum.Enum):
    RECEIVED = "received"          # تم الاستلام
    NOT_REPAIRED = "not_repaired"  # لم تتم الصيانة
    REPAIRED = "repaired"          # تم الصيانة
    DELIVERED = "delivered"        # تم التسليم

class MaintenanceJob(Base):
    """نموذج طلبات الصيانة"""
    __tablename__ = "maintenance_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    tracking_code = Column(String(20), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    technician_id = Column(Integer, ForeignKey("users.id"), index=True)
    device_type = Column(String(100), nullable=False, index=True)
    device_model = Column(String(100))
    serial_number = Column(String(100), index=True)
    issue_description = Column(Text, nullable=False)
    status = Column(Enum(MaintenanceStatus), default=MaintenanceStatus.RECEIVED, nullable=False, index=True)
    estimated_cost = Column(Float, default=0.0)
    final_cost = Column(Float)
    notes = Column(Text)
    
    # حقول العملة
    estimated_cost_currency = Column(String(3), default="USD")  # العملة للتكلفة التقديرية
    final_cost_currency = Column(String(3), default="USD")  # العملة للتكلفة النهائية
    
    # حقول الدفع
    payment_status = Column(String(20), default="unpaid", index=True)  # paid أو unpaid
    payment_method = Column(String(20))  # cash أو wish_money (فقط إذا كان paid)
    payment_date = Column(DateTime, index=True)  # تاريخ الدفع
    
    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    delivered_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    customer = relationship("Customer", back_populates="maintenance_jobs")
    technician = relationship("User", back_populates="maintenance_jobs")
    parts = relationship("UsedPart", back_populates="maintenance_job")
    expenses = relationship("JobExpense", back_populates="job", cascade="all, delete-orphan")
    status_history = relationship("StatusHistory", back_populates="maintenance_job")
    payments = relationship("Payment", back_populates="maintenance_job")

class Part(Base):
    """نموذج قطع الغيار"""
    __tablename__ = "parts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Float, default=0.0)
    quantity = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    used_in = relationship("UsedPart", back_populates="part")

class UsedPart(Base):
    """نموذج قطع الغيار المستخدمة في الصيانة"""
    __tablename__ = "used_parts"
    
    id = Column(Integer, primary_key=True, index=True)
    maintenance_job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # العلاقات
    maintenance_job = relationship("MaintenanceJob", back_populates="parts")
    part = relationship("Part", back_populates="used_in")

class JobExpense(Base):
    """المصاريف المرتبطة بطلب الصيانة"""
    __tablename__ = "job_expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    maintenance_job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    description = Column(String(200), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    category = Column(String(50), default="general")
    is_included = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # العلاقات
    job = relationship("MaintenanceJob", back_populates="expenses")

class StatusHistory(Base):
    """سجل تغييرات حالة الصيانة"""
    __tablename__ = "status_history"
    
    id = Column(Integer, primary_key=True, index=True)
    maintenance_job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    status = Column(Enum(MaintenanceStatus), nullable=False)
    notes = Column(Text)
    changed_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # العلاقات
    maintenance_job = relationship("MaintenanceJob", back_populates="status_history")
    changed_by = relationship("User")

class PaymentStatus(str, enum.Enum):
    UNPAID = "unpaid"      # دين (غير مدفوع)
    PAID = "paid"          # مدفوع بالكامل

class PaymentMethod(str, enum.Enum):
    CASH = "cash"          # كاش
    WISH_MONEY = "wish_money"  # ويش موني

class Payment(Base):
    """نموذج المدفوعات"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    maintenance_job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50))
    status = Column(Enum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    maintenance_job = relationship("MaintenanceJob", back_populates="payments")

class SystemSettings(Base):
    """نموذج إعدادات النظام"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, nullable=False)
    setting_value = Column(Text)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VIPCustomer(Base):
    """نموذج العملاء المميزين"""
    __tablename__ = "vip_customers"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), unique=True, nullable=False, index=True)
    whatsapp_number = Column(String(20), index=True)  # رقم واتساب
    whatsapp_enabled = Column(Boolean, default=True, index=True)  # تفعيل إرسال واتساب
    account_enabled = Column(Boolean, default=True, index=True)  # تفعيل الحساب
    credit_limit = Column(Float, default=0.0)  # حد الائتمان
    notes = Column(Text)  # ملاحظات
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    customer = relationship("Customer")
    whatsapp_schedules = relationship("WhatsAppSchedule", back_populates="vip_customer")
    account_transactions = relationship("AccountTransaction", back_populates="vip_customer")

class WhatsAppSchedule(Base):
    """نموذج جدولة رسائل واتساب للعملاء المميزين"""
    __tablename__ = "whatsapp_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    vip_customer_id = Column(Integer, ForeignKey("vip_customers.id"), nullable=False)
    message_type = Column(String(50))  # نوع الرسالة (status_update, reminder, etc)
    message_text = Column(Text)
    send_time = Column(String(10))  # وقت الإرسال (HH:MM)
    send_days = Column(String(50))  # أيام الإرسال (JSON array)
    is_active = Column(Boolean, default=True)
    last_sent = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    vip_customer = relationship("VIPCustomer", back_populates="whatsapp_schedules")

class AccountTransaction(Base):
    """نموذج المعاملات الحسابية للعملاء المميزين"""
    __tablename__ = "account_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    vip_customer_id = Column(Integer, ForeignKey("vip_customers.id"), nullable=False, index=True)
    maintenance_job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), index=True)
    transaction_type = Column(String(20), nullable=False, index=True)  # debt, payment, adjustment
    amount = Column(Float, nullable=False)
    payment_method = Column(String(20))  # cash, wish_money, credit
    description = Column(Text)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # العلاقات
    vip_customer = relationship("VIPCustomer", back_populates="account_transactions")
    maintenance_job = relationship("MaintenanceJob")
    created_by = relationship("User")
