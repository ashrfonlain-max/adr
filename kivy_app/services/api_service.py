"""
خدمة API للاتصال بـ Flask API - محسّنة للأداء والموثوقية
"""

import requests
from typing import Optional, Tuple, Dict, Any, List
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIService:
    """خدمة API محسّنة مع Retry و Timeout"""
    
    def __init__(self, base_url: str = "http://localhost:5000/api"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token = None
        self.timeout = 30  # 30 ثانية timeout
        
        # إضافة retry strategy للتعامل مع مشاكل الشبكة
        retry_strategy = Retry(
            total=3,  # 3 محاولات
            backoff_factor=1,  # انتظار 1, 2, 4 ثواني
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def login(self, password: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """تسجيل الدخول (يستخدم كلمة مرور بسيطة)"""
        try:
            # Flask API يستخدم كلمة مرور بسيطة
            response = self.session.post(
                f"{self.base_url.replace('/api', '')}/login",
                data={'password': password},
                allow_redirects=False
            )
            
            # التحقق من نجاح تسجيل الدخول
            if response.status_code == 302 or response.status_code == 200:
                # حفظ cookie للجلسة
                return True, None, {'authenticated': True}
            else:
                return False, "كلمة المرور غير صحيحة", None
        except Exception as e:
            return False, f"خطأ في الاتصال: {str(e)}", None
    
    def get_jobs(self, status: Optional[str] = None, search: Optional[str] = None) -> Tuple[bool, List[Dict]]:
        """جلب قائمة الطلبات - محسّن مع Retry"""
        max_retries = 2  # محاولات أقل للقراءة
        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}/jobs"
                params = []
                if status:
                    params.append(f"status={status}")
                if search:
                    params.append(f"search={search}")
                
                if params:
                    url += "?" + "&".join(params)
                
                response = self.session.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    data = response.json()
                    return True, data.get('jobs', [])
                else:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return False, []
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return False, []
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return False, []
            except Exception as e:
                return False, []
    
    def get_job(self, job_id: int) -> Tuple[bool, Optional[Dict]]:
        """جلب تفاصيل طلب"""
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}")
            
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, None
        except Exception as e:
            return False, None
    
    def create_job(self, data: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """إنشاء طلب جديد - محسّن مع Retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    f"{self.base_url}/jobs",
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    if result.get('success'):
                        return True, None, result.get('job')
                    else:
                        return False, result.get('message', 'فشل إنشاء الطلب'), None
                else:
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))  # exponential backoff
                        continue
                    return False, "فشل إنشاء الطلب", None
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, "انتهت مهلة الاتصال. تحقق من الإنترنت وحاول مرة أخرى", None
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                return False, "فشل الاتصال بالخادم. تحقق من الإنترنت", None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, f"خطأ في الاتصال: {str(e)}", None
        return False, "فشل بعد 3 محاولات", None
    
    def update_job(self, job_id: int, data: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """تحديث طلب - محسّن مع Retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.put(
                    f"{self.base_url}/jobs/{job_id}",
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        return True, None, result.get('job')
                    else:
                        return False, result.get('message', 'فشل تحديث الطلب'), None
                else:
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    return False, "فشل تحديث الطلب", None
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, "انتهت مهلة الاتصال. حاول مرة أخرى", None
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                return False, "فشل الاتصال بالخادم", None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, f"خطأ في الاتصال: {str(e)}", None
        return False, "فشل بعد 3 محاولات", None
    
    def update_job_status(self, job_id: int, status: str, **kwargs) -> Tuple[bool, Optional[str]]:
        """تحديث حالة الطلب - محسّن مع Retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                data = {'status': status, **kwargs}
                response = self.session.put(
                    f"{self.base_url}/jobs/{job_id}/status",
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        return True, None
                    else:
                        return False, result.get('message', 'فشل تحديث الحالة')
                else:
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    return False, "فشل تحديث الحالة"
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, "انتهت مهلة الاتصال. حاول مرة أخرى"
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                return False, "فشل الاتصال بالخادم"
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return False, f"خطأ في الاتصال: {str(e)}"
        return False, "فشل بعد 3 محاولات"
    
    def update_payment_status(self, job_id: int, payment_status: str, payment_method: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """تحديث حالة الدفع"""
        try:
            data = {'payment_status': payment_status}
            if payment_method:
                data['payment_method'] = payment_method
            
            response = self.session.put(
                f"{self.base_url}/jobs/{job_id}/payment",
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return True, result.get('message')
                else:
                    return False, result.get('message', 'فشل تحديث حالة الدفع')
            else:
                return False, "فشل تحديث حالة الدفع"
        except Exception as e:
            return False, f"خطأ في الاتصال: {str(e)}"
    
    def delete_job(self, job_id: int) -> Tuple[bool, Optional[str]]:
        """حذف طلب"""
        try:
            response = self.session.delete(f"{self.base_url}/jobs/{job_id}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return True, result.get('message')
                else:
                    return False, result.get('message', 'فشل حذف الطلب')
            else:
                return False, "فشل حذف الطلب"
        except Exception as e:
            return False, f"خطأ في الاتصال: {str(e)}"
    
    def get_stats(self) -> Tuple[bool, Optional[Dict]]:
        """جلب الإحصائيات"""
        try:
            response = self.session.get(f"{self.base_url}/stats")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return True, data.get('stats')
            return False, None
        except Exception as e:
            return False, None
    
    def get_debts(self) -> Tuple[bool, List[Dict]]:
        """جلب قائمة الديون"""
        try:
            response = self.session.get(f"{self.base_url}/debts")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return True, data.get('debts', [])
            return False, []
        except Exception as e:
            return False, []

