"""
نظام Cache ذكي متقدم للأداء الخارق
"""

import time
import threading
from typing import Any, Callable, Optional, Dict
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import json

class SmartCache:
    """نظام Cache ذكي مع TTL و invalidation تلقائي"""
    
    def __init__(self, default_ttl: int = 60):
        """
        default_ttl: الوقت الافتراضي للـ cache بالثواني
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str, default: Any = None) -> Any:
        """الحصول على قيمة من الـ cache"""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                # التحقق من انتهاء الصلاحية
                if time.time() < entry['expires_at']:
                    self._hits += 1
                    return entry['value']
                else:
                    # حذف الإدخال المنتهي
                    del self._cache[key]
            
            self._misses += 1
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """حفظ قيمة في الـ cache"""
        with self._lock:
            ttl = ttl or self.default_ttl
            self._cache[key] = {
                'value': value,
                'expires_at': time.time() + ttl,
                'created_at': time.time()
            }
    
    def delete(self, key: str) -> None:
        """حذف مفتاح من الـ cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self) -> None:
        """مسح جميع الـ cache"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def invalidate_pattern(self, pattern: str) -> None:
        """حذف جميع المفاتيح التي تحتوي على pattern"""
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات الـ cache"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'size': len(self._cache)
            }
    
    def cleanup_expired(self) -> None:
        """تنظيف الإدخالات المنتهية"""
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._cache.items()
                if now >= v['expires_at']
            ]
            for key in expired_keys:
                del self._cache[key]

# Cache عام للتطبيق
app_cache = SmartCache(default_ttl=30)

def cached(ttl: int = 30, key_func: Optional[Callable] = None):
    """
    ديكوريتر للـ cache تلقائي
    
    Usage:
        @cached(ttl=60)
        def my_function(arg1, arg2):
            return expensive_operation()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # إنشاء مفتاح فريد
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # مفتاح افتراضي من اسم الدالة والوسائط
                key_parts = [func.__name__]
                key_parts.extend([str(arg) for arg in args])
                key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
                cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
            
            # محاولة الحصول من الـ cache
            cached_value = app_cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # تنفيذ الدالة وحفظ النتيجة
            result = func(*args, **kwargs)
            app_cache.set(cache_key, result, ttl)
            return result
        
        # إضافة دالة لإلغاء الـ cache
        wrapper.cache_clear = lambda: app_cache.invalidate_pattern(func.__name__)
        return wrapper
    return decorator

def cache_key_builder(*args, **kwargs) -> str:
    """بناء مفتاح cache من الوسائط"""
    parts = []
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            parts.append(str(arg))
        elif hasattr(arg, 'id'):
            parts.append(f"{type(arg).__name__}:{arg.id}")
        else:
            parts.append(str(hash(str(arg))))
    
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    
    return hashlib.md5("|".join(parts).encode()).hexdigest()














