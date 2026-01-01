"""
خدمات إدارة المستخدمين والمصادقة
"""

from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database.models import User
from utils.auth import verify_password, hash_password


class UserService:
    """خدمة للتعامل مع المستخدمين وتسجيل الدخول"""

    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        """التحقق من بيانات الدخول"""
        try:
            user = (
                self.db.query(User)
                .filter(User.username == username)
                .filter(User.is_active.is_(True))
                .first()
            )

            if not user:
                return False, "اسم المستخدم غير صحيح أو الحساب غير مفعل.", None

            if not verify_password(user.password_hash, password):
                return False, "كلمة المرور غير صحيحة.", None

            user.last_login_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return True, "تم تسجيل الدخول بنجاح.", user
        except SQLAlchemyError as exc:
            self.db.rollback()
            return False, f"حدث خطأ أثناء التحقق: {str(exc)}", None

    def create_user(self, username: str, password: str, full_name: str, role: str) -> Tuple[bool, str, Optional[User]]:
        """إنشاء مستخدم جديد"""
        try:
            existing = (
                self.db.query(User)
                .filter(User.username == username)
                .first()
            )
            if existing:
                return False, "اسم المستخدم مستخدم بالفعل.", None

            user = User(
                username=username,
                full_name=full_name,
                role=role,
                password_hash=hash_password(password),
                is_active=True
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return True, "تم إنشاء المستخدم بنجاح.", user
        except SQLAlchemyError as exc:
            self.db.rollback()
            return False, f"فشل إنشاء المستخدم: {str(exc)}", None

