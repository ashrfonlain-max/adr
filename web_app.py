"""
تطبيق ويب للتحكم بنظام الصيانة من الهاتف
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from database.connection import get_db
from services.maintenance_service import MaintenanceService
from database.models import MaintenanceJob, Customer
from datetime import datetime, timedelta
import urllib.parse
import secrets
import hashlib
import config
import warnings
import logging

# إخفاء تحذير development server
warnings.filterwarnings('ignore', message='.*development server.*')
warnings.filterwarnings('ignore', category=UserWarning)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app)  # للسماح بالوصول من أي جهاز

# إعدادات الأمان
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# كلمة مرور الوصول عن بُعد (من متغيرات البيئة)
REMOTE_ACCESS_PASSWORD = config.REMOTE_ACCESS_PASSWORD or "adr2024"  # قيمة افتراضية مؤقتة

def check_auth():
    """التحقق من المصادقة"""
    if request.remote_addr in ['127.0.0.1', '::1', 'localhost']:
        # الوصول المحلي لا يحتاج مصادقة
        return True
    
    # الوصول عن بُعد يحتاج مصادقة
    return session.get('authenticated', False)

def require_auth(f):
    """ديكوريتر للمصادقة"""
    def decorated_function(*args, **kwargs):
        if not check_auth():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def generate_whatsapp_notification(job_id, status, price="", price_currency=None):
    """إنشاء رابط إشعار WhatsApp"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        # استخدام الرسالة المخصصة
        message = service.generate_custom_whatsapp_message(job_id, status, price, price_currency)
        
        if not message:
            return None
        
        # الحصول على بيانات العميل للهاتف
        job = db.query(MaintenanceJob).filter_by(id=job_id).first()
        if not job:
            return None
        
        # إنشاء رابط WhatsApp
        phone = job.customer.phone.replace('+', '').replace(' ', '')
        if not phone.startswith('961'):
            phone = '961' + phone.lstrip('0')
        
        whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
        return whatsapp_url
        
    except Exception as e:
        print(f"خطأ في إنشاء رابط WhatsApp: {e}")
        return None
    finally:
        db.close()

# صفحة تسجيل الدخول
@app.route('/login', methods=['GET', 'POST'])
def login():
    """صفحة تسجيل الدخول للوصول عن بُعد"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == REMOTE_ACCESS_PASSWORD:
            session['authenticated'] = True
            session.permanent = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='كلمة المرور غير صحيحة')
    
    return render_template('login.html')

# تسجيل الخروج
@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    session.pop('authenticated', None)
    return redirect(url_for('login'))

# الصفحة الرئيسية
@app.route('/')
@require_auth
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html', enable_monthly_stats=config.ENABLE_MONTHLY_STATS)

# PWA Routes
@app.route('/manifest.json')
def manifest():
    """PWA Manifest"""
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def service_worker():
    """Service Worker"""
    return app.send_static_file('sw.js')

@app.route('/offline.html')
def offline():
    """صفحة عدم الاتصال"""
    return app.send_static_file('offline.html')

# API: الحصول على جميع الطلبات
@app.route('/api/jobs', methods=['GET'])
@require_auth
def get_jobs():
    """الحصول على جميع طلبات الصيانة"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        # البحث إذا كان موجود
        query = request.args.get('search', '')
        status = request.args.get('status', '')
        
        success, message, jobs = service.search_jobs(
            query=query if query else None,
            status=status if status else None,
            limit=100
        )
        
        if success:
            return jsonify({
                'success': True,
                'jobs': jobs
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: الحصول على تفاصيل طلب معين
@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    """الحصول على تفاصيل طلب معين"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, job = service.get_job_details(job_id)
        
        if success:
            return jsonify({
                'success': True,
                'job': job
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: إضافة طلب جديد
@app.route('/api/jobs', methods=['POST'])
def create_job():
    """إضافة طلب صيانة جديد"""
    try:
        data = request.json
        
        # التحقق من البيانات المطلوبة (وصف العطل اختياري الآن)
        required_fields = ['customer_name', 'phone', 'device_type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'الحقل {field} مطلوب'
                }), 400
        
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, job = service.create_maintenance_job(
            customer_name=data['customer_name'],
            phone=data['phone'],
            device_type=data['device_type'],
            device_model=data.get('device_model'),
            serial_number=data.get('serial_number'),
            issue_description=data.get('issue_description', 'غير محدد'),  # قيمة افتراضية إذا كان فارغاً
            estimated_cost=float(data.get('estimated_cost', 0)),
            estimated_cost_currency=data.get('estimated_cost_currency', 'USD'),
            notes=data.get('notes'),
            code_type=data.get('code_type', 'A')
        )
        
        # إذا تم إنشاء الطلب بنجاح وتم تحديد طريقة دفع، قم بتحديثها
        if success and data.get('payment_method'):
            payment_method = data['payment_method']
            if payment_method in ['cash', 'wish_money']:
                # تحديث طريقة الدفع في قاعدة البيانات
                try:
                    from database.models import MaintenanceJob
                    job_obj = db.query(MaintenanceJob).filter_by(id=job['id']).first()
                    if job_obj:
                        job_obj.payment_method = payment_method
                        db.commit()
                except Exception as e:
                    print(f"تحذير: فشل في تحديث طريقة الدفع: {e}")
        
        # إنشاء QR Code تلقائياً عند إنشاء طلب جديد
        if success and job and job.get('tracking_code'):
            try:
                from utils.barcode_generator import BarcodeGenerator
                import os
                
                # إنشاء مجلد QR codes إذا لم يكن موجوداً
                qr_dir = "static/qrcodes"
                os.makedirs(qr_dir, exist_ok=True)
                
                generator = BarcodeGenerator(output_dir=qr_dir)
                
                # إنشاء رابط التتبع
                base_url = request.host_url.rstrip('/')
                track_url = f"{base_url}/track?code={job['tracking_code']}"
                
                # إنشاء QR Code
                qr_path = generator.generate_qr_code(track_url, size=10)
                print(f"✅ تم إنشاء QR Code للطلب {job['tracking_code']}: {qr_path}")
            except Exception as e:
                print(f"⚠️ تحذير: فشل في إنشاء QR Code: {e}")
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'job': job,
                'qr_code_url': f"/api/qr/{job['tracking_code']}" if job and job.get('tracking_code') else None
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: تحديث حالة طلب
@app.route('/api/jobs/<int:job_id>/status', methods=['PUT'])
def update_job_status(job_id):
    """تحديث حالة طلب الصيانة"""
    try:
        data = request.json
        
        if 'status' not in data:
            return jsonify({
                'success': False,
                'message': 'الحقل status مطلوب'
            }), 400
        
        db = next(get_db())
        service = MaintenanceService(db)
        
        # إنشاء ملاحظات مع السعر ونوع العطل
        notes = data.get('notes', '')
        price = data.get('price', '')
        issue_type = data.get('issue_type', '')
        price_currency = (data.get('price_currency') or 'USD').upper()
        
        if data['status'] == 'repaired' and price:
            if not notes:
                notes = "تمت الصيانة"
            if price_currency == "LBP":
                notes += f"\nالسعر: {price} ل.ل"
            else:
                notes += f"\nالسعر: ${price}"
            if issue_type:
                notes += f"\nنوع العطل: {issue_type}"
            
            # تحديث السعر النهائي في قاعدة البيانات
            try:
                price_float = float(price)
                price_value = price_float
                if price_currency == "LBP":
                    price_value = service.convert_currency(price_float, "LBP", "USD")
                update_success, update_message = service.update_maintenance_job(
                    job_id=job_id,
                    final_cost=price_value,
                    final_cost_currency=price_currency
                )
                if not update_success:
                    print(f"تحذير: فشل في تحديث السعر: {update_message}")
            except ValueError:
                print(f"تحذير: السعر غير صالح: {price}")
        
        success, message = service.update_job_status(
            job_id=job_id,
            new_status=data['status'],
            notes=notes,
            user_id=1
        )
        
        if success:
            # إرسال إشعار WhatsApp إذا كان متاحاً
            try:
                whatsapp_url = generate_whatsapp_notification(job_id, data['status'], data.get('price', ''), price_currency)
                if whatsapp_url:
                    return jsonify({
                        'success': True,
                        'message': message,
                        'whatsapp_url': whatsapp_url,
                        'whatsapp_sent': True
                    })
            except Exception as e:
                print(f"تحذير: فشل في إنشاء رابط WhatsApp: {e}")
            
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()


# API: حذف طلب
@app.route('/api/jobs/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    """حذف طلب صيانة"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message = service.delete_job(job_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: تحديث بيانات الطلب
@app.route('/api/jobs/<int:job_id>', methods=['PUT'])
def update_job(job_id):
    """تحديث بيانات طلب الصيانة"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        data = request.get_json()
        
        success, message = service.update_maintenance_job(
            job_id=job_id,
            device_type=data.get('device_type'),
            device_model=data.get('device_model'),
            serial_number=data.get('serial_number'),
            issue_description=data.get('issue_description'),
            notes=data.get('notes'),
            final_cost=data.get('final_cost'),
            final_cost_currency=data.get('final_cost_currency'),
            tracking_code=data.get('tracking_code')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: تحديث حالة الدفع
@app.route('/api/jobs/<int:job_id>/payment', methods=['PUT'])
def update_payment_status(job_id):
    """تحديث حالة الدفع"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        data = request.get_json()
        payment_status = data.get('payment_status')
        payment_method = data.get('payment_method')
        
        success, message = service.update_payment_status(
            job_id=job_id,
            payment_status=payment_status,
            payment_method=payment_method
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: الحصول على قائمة الديون
@app.route('/api/debts', methods=['GET'])
def get_debts():
    """الحصول على قائمة الديون"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, debts = service.get_unpaid_jobs()
        
        if success:
            return jsonify({
                'success': True,
                'debts': debts
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: ملخص المدفوعات
@app.route('/api/payment-summary', methods=['GET'])
def get_payment_summary():
    """الحصول على ملخص المدفوعات"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, summary = service.get_payment_summary()
        
        if success:
            return jsonify({
                'success': True,
                'summary': summary
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: إحصائيات
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """الحصول على إحصائيات النظام"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, stats = service.get_dashboard_stats()
        
        if success:
            return jsonify({
                'success': True,
                'stats': stats
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: إدارة إعدادات النظام
@app.route('/api/settings', methods=['GET'])
def get_settings():
    """الحصول على إعدادات النظام"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        settings = {
            'whatsapp_message_template': service.get_system_setting(
                'whatsapp_message_template',
                '🔧 تحديث حالة طلب الصيانة\nرقم التتبع: {tracking_code}\nالعميل: {customer_name}\nالجهاز: {device_type}\nالموديل: {device_model}\nالرقم التسلسلي: {serial_number}\nالحالة الجديدة: {status}\n{price_info}\nتاريخ التحديث: {date}\nشكراً لثقتكم بنا! 🙏'
            ),
            'exchange_rate': config.EXCHANGE_RATE,
            'default_currency': config.DEFAULT_CURRENCY
        }
        
        return jsonify({
            'success': True,
            'settings': settings
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """تحديث إعدادات النظام"""
    try:
        data = request.json
        
        db = next(get_db())
        service = MaintenanceService(db)
        
        # تحديث قالب رسالة الواتساب
        if 'whatsapp_message_template' in data:
            success, message = service.set_system_setting(
                'whatsapp_message_template',
                data['whatsapp_message_template'],
                'قالب رسالة الواتساب المخصصة'
            )
            if not success:
                return jsonify({
                    'success': False,
                    'message': message
                }), 400
        
        return jsonify({
            'success': True,
            'message': 'تم تحديث الإعدادات بنجاح'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: تحديث كود التتبع
@app.route('/api/jobs/<int:job_id>/tracking-code', methods=['PUT'])
def update_tracking_code(job_id):
    """تحديث كود التتبع لطلب الصيانة"""
    try:
        data = request.json
        
        if 'tracking_code' not in data:
            return jsonify({
                'success': False,
                'message': 'الحقل tracking_code مطلوب'
            }), 400
        
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message = service.update_maintenance_job(
            job_id=job_id,
            tracking_code=data['tracking_code']
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: الحصول على أكواد التتبع المتاحة
@app.route('/api/tracking-codes/<code_type>', methods=['GET'])
def get_available_tracking_codes(code_type):
    """الحصول على قائمة بالأكواد المتاحة لنوع معين"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        available_codes = service.get_available_tracking_codes(code_type)
        
        return jsonify({
            'success': True,
            'codes': available_codes
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: الحصول على بيانات التقرير
@app.route('/api/reports', methods=['GET'])
@require_auth
def get_reports():
    """الحصول على بيانات التقرير"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        # الحصول على معاملات التقرير
        report_type = request.args.get('report_type', 'daily')
        code_type = request.args.get('code_type', None)
        status = request.args.get('status', 'delivered')
        start_date_str = request.args.get('start_date', None)
        end_date_str = request.args.get('end_date', None)
        
        # تحويل التواريخ إذا كانت موجودة
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'صيغة تاريخ البداية غير صحيحة. استخدم YYYY-MM-DD'
                }), 400
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': 'صيغة تاريخ النهاية غير صحيحة. استخدم YYYY-MM-DD'
                }), 400
        
        success, message, report_data = service.get_report_data(
            report_type=report_type,
            code_type=code_type,
            status=status if status != 'all' else None,
            start_date=start_date,
            end_date=end_date
        )
        
        if success:
            return jsonify({
                'success': True,
                'report': report_data
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: تتبع الجهاز للعملاء (بدون مصادقة)
@app.route('/api/track/<tracking_code>', methods=['GET'])
def track_device(tracking_code):
    """تتبع جهاز باستخدام رقم التتبع - للعملاء"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, device = service.get_job_by_tracking_code(tracking_code)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'device': device
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: إنشاء QR Code للجهاز
@app.route('/api/qr/<tracking_code>', methods=['GET'])
def generate_qr_code(tracking_code):
    """إنشاء QR Code لرقم التتبع"""
    try:
        from utils.barcode_generator import BarcodeGenerator
        import os
        from flask import send_file
        
        # التحقق من وجود الطلب
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, device = service.get_job_by_tracking_code(tracking_code)
        if not success:
            return jsonify({
                'success': False,
                'message': message
            }), 404
        
        # إنشاء مجلد QR codes إذا لم يكن موجوداً
        qr_dir = "static/qrcodes"
        os.makedirs(qr_dir, exist_ok=True)
        
        # التحقق من وجود QR Code مسبقاً
        qr_filename = f"qr_{tracking_code}.png"
        qr_path = os.path.join(qr_dir, qr_filename)
        
        # إذا كان QR Code موجوداً، أرجع الملف الموجود
        if os.path.exists(qr_path):
            return send_file(qr_path, mimetype='image/png', as_attachment=False)
        
        # إنشاء QR Code جديد
        generator = BarcodeGenerator(output_dir=qr_dir)
        
        # إنشاء رابط التتبع
        base_url = request.host_url.rstrip('/')
        track_url = f"{base_url}/track?code={tracking_code}"
        
        # إنشاء QR Code
        generated_path = generator.generate_qr_code(track_url, size=10)
        
        # إعادة تسمية الملف ليكون ثابتاً
        if generated_path != qr_path:
            if os.path.exists(qr_path):
                os.remove(qr_path)
            os.rename(generated_path, qr_path)
        else:
            qr_path = generated_path
        
        # إرجاع الصورة
        return send_file(qr_path, mimetype='image/png', as_attachment=False)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# API: تحميل QR Code كملف
@app.route('/api/qr/<tracking_code>/download', methods=['GET'])
def download_qr_code(tracking_code):
    """تحميل QR Code كملف"""
    try:
        from flask import send_file
        import os
        
        # التحقق من وجود الطلب
        db = next(get_db())
        service = MaintenanceService(db)
        
        success, message, device = service.get_job_by_tracking_code(tracking_code)
        if not success:
            return jsonify({
                'success': False,
                'message': message
            }), 404
        
        # مسار QR Code
        qr_dir = "static/qrcodes"
        qr_filename = f"qr_{tracking_code}.png"
        qr_path = os.path.join(qr_dir, qr_filename)
        
        # إذا لم يكن موجوداً، أنشئه
        if not os.path.exists(qr_path):
            # استدعاء API إنشاء QR Code
            from utils.barcode_generator import BarcodeGenerator
            os.makedirs(qr_dir, exist_ok=True)
            generator = BarcodeGenerator(output_dir=qr_dir)
            base_url = request.host_url.rstrip('/')
            track_url = f"{base_url}/track?code={tracking_code}"
            generated_path = generator.generate_qr_code(track_url, size=10)
            if generated_path != qr_path:
                if os.path.exists(qr_path):
                    os.remove(qr_path)
                os.rename(generated_path, qr_path)
        
        # إرجاع الملف للتحميل
        return send_file(qr_path, mimetype='image/png', as_attachment=True, 
                        download_name=f'QR_Code_{tracking_code}.png')
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

# صفحة الشركة الرئيسية (للعملاء)
@app.route('/home')
def home():
    """الصفحة الرئيسية للشركة"""
    return render_template('home.html')

# صفحة تتبع الجهاز (للعملاء)
@app.route('/track')
def track():
    """صفحة تتبع الجهاز للعملاء"""
    return render_template('track.html')

# صفحة من نحن (للعملاء)
@app.route('/about')
def about():
    """صفحة من نحن للعملاء"""
    return render_template('about.html')

# API: الحصول على الأجهزة القديمة المعلقة
@app.route('/api/pending-old-jobs', methods=['GET'])
@require_auth
def get_pending_old_jobs():
    """الحصول على قائمة الأجهزة القديمة المعلقة"""
    try:
        db = next(get_db())
        service = MaintenanceService(db)
        
        # الحصول على عدد الأيام من المعاملات (افتراضي: 30 يوم)
        days_threshold = request.args.get('days', 30, type=int)
        # الحصول على الحالة من المعاملات (اختياري: 'received' أو 'repaired')
        status = request.args.get('status', None)
        
        success, message, jobs = service.get_pending_old_jobs(
            days_threshold=days_threshold,
            status=status
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'jobs': jobs,
                'count': len(jobs)
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        db.close()

if __name__ == '__main__':
    # تشغيل السيرفر
    # استخدم host='0.0.0.0' للسماح بالوصول من أي جهاز في الشبكة
    import os
    
    # الحصول على المنفذ من متغيرات البيئة (للخوادم السحابية) أو استخدام 5000 افتراضياً
    port = int(os.environ.get('PORT', 5000))
    
    # تحديد وضع التشغيل (الإنتاج أو التطوير)
    debug_mode = os.environ.get('FLASK_ENV', 'development') != 'production'
    
    print("\n" + "="*60)
    print("🌐 تطبيق الويب يعمل!")
    print("="*60)
    print("📱 للوصول محلياً:")
    print(f"   http://localhost:{port}")
    
    # محاولة الحصول على IP Address (للشبكة المحلية فقط)
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"\n📱 للوصول من الهاتف (نفس WiFi):")
        print(f"   http://{local_ip}:{port}")
    except:
        pass
    
    print(f"\n🔑 كلمة المرور: {REMOTE_ACCESS_PASSWORD}")
    print("="*60 + "\n")
    
    # إخفاء تحذير development server (تم إعداده في الأعلى)
    # دعم متغيرات البيئة للاستضافة السحابية (Railway, Render, etc.)
    # في الإنتاج، تعطيل debug دائماً
    if os.environ.get('PORT'):
        debug_mode = False  # تعطيل debug في الإنتاج (Railway, Render, etc.)
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

