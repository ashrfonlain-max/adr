"""
وحدة المصادقة وكلمات المرور
"""
import hashlib
import os
import binascii

def hash_password(password: str, salt: str = None) -> str:
    """
    تشفير كلمة المرور باستخدام خوارزمية PBKDF2 مع HMAC-SHA256
    
    Args:
        password: كلمة المرور النصية
        salt: الملح (اختياري، سيتم إنشاؤه تلقائياً إذا لم يتم توفيره)
        
    Returns:
        سلسلة نصية تحتوي على: الخوارزمية$عدد التكرارات$الملح$التجزئة
    """
    # إعداد المعلمات
    algorithm = 'pbkdf2_sha256'
    iterations = 260000
    
    # إنشاء ملح عشوائي إذا لم يتم توفيره
    if salt is None:
        salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    else:
        salt = salt.encode('ascii')
    
    # تشفير كلمة المرور
    pwdhash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations
    )
    
    # تنسيق النتيجة
    pwdhash = binascii.hexlify(pwdhash).decode('ascii')
    
    # إرجاع النتيجة بصيغة: algorithm$iterations$salt$hash
    return f"{algorithm}${iterations}${salt.decode('ascii')}${pwdhash}"

def verify_password(stored_password: str, provided_password: str) -> bool:
    """
    التحقق من صحة كلمة المرور
    
    Args:
        stored_password: كلمة المرور المشفرة المخزنة
        provided_password: كلمة المرور المدخلة للتحقق منها
        
    Returns:
        True إذا كانت كلمة المرور صحيحة، False إذا لم تكن صحيحة
    """
    try:
        # تحليل كلمة المرور المخزنة
        algorithm, iterations, salt, pwdhash = stored_password.split('$', 3)
        
        # تشفير كلمة المرور المدخلة باستخدام نفس المعلمات
        new_hash = hash_password(provided_password, salt).split('$')[-1]
        
        # مقارنة التجزئة
        return new_hash == pwdhash
    except (ValueError, IndexError):
        return False

def generate_api_key() -> str:
    """
    إنشاء مفتاح واجهة برمجة تطبيقات (API) عشوائي
    
    Returns:
        مفتاح API عشوائي
    """
    return hashlib.sha256(os.urandom(32)).hexdigest()
