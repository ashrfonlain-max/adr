import sqlite3
from datetime import datetime
import random
import string

class CodeService:
    def __init__(self, db_path):
        self.db_path = db_path
        self._create_tables()
    
    def _create_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # إنشاء جدول لتخزين الأجهزة ورموزها
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS device_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_serial TEXT UNIQUE,
                    barcode TEXT UNIQUE,
                    device_type TEXT,
                    device_model TEXT,
                    customer_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP
                )
            ''')
            conn.commit()
    
    def generate_unique_code(self, prefix='A'):
        """توليد كود فريد للجهاز يبدأ من A1"""
        # الحصول على آخر كود تم إنشاؤه
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT barcode FROM device_codes 
                WHERE barcode LIKE ? 
                ORDER BY id DESC 
                LIMIT 1
            ''', (f"{prefix}%",))
            
            result = cursor.fetchone()
            
            if not result:
                # إذا لم توجد أي أكواد، ابدأ من A1
                return f"{prefix}1"
            
            # استخراج الرقم من آخر كود
            last_code = result[0]
            if last_code.startswith(prefix):
                try:
                    # استخراج الرقم من الكود (مثل A1 -> 1)
                    number = int(last_code[1:])
                    new_number = number + 1
                    return f"{prefix}{new_number}"
                except ValueError:
                    # إذا فشل في استخراج الرقم، ابدأ من A1
                    return f"{prefix}1"
            else:
                # إذا لم يبدأ الكود بالبادئة المطلوبة، ابدأ من A1
                return f"{prefix}1"
    
    def _code_exists(self, code, code_type='barcode'):
        """التحقق من وجود الكود في قاعدة البيانات"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT 1 FROM device_codes WHERE {code_type} = ?', (code,))
            return cursor.fetchone() is not None
    
    def save_device_code(self, device_data):
        """حفظ بيانات الجهاز والكود"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO device_codes 
                (device_serial, barcode, device_type, device_model, customer_name, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                device_data.get('serial_number'),
                device_data.get('barcode', self.generate_unique_code()),
                device_data.get('device_type'),
                device_data.get('device_model'),
                device_data.get('customer_name'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            conn.commit()
    
    def find_device_by_code(self, code):
        """البحث عن جهاز باستخدام الكود أو الباركود"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM device_codes 
                WHERE device_serial = ? OR barcode = ?
                ORDER BY last_used_at DESC
                LIMIT 1
            ''', (code, code))
            
            result = cursor.fetchone()
            if result:
                # تحديث وقت آخر استخدام
                cursor.execute('''
                    UPDATE device_codes 
                    SET last_used_at = ? 
                    WHERE id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), result['id']))
                conn.commit()
                
                # تحويل النتيجة إلى قاموس
                return dict(result)
            return None
