"""
وحدة إرسال الإشعارات عبر البريد الإلكتروني والرسائل النصية
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Tuple
import logging
import requests
from jinja2 import Environment, FileSystemLoader

# تكوين السجل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService:
    """خدمة إرسال الإشعارات"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        تهيئة خدمة الإشعارات
        
        المعلمات:
            config: قاموس يحتوي على إعدادات الإشعارات (SMTP، SMS API، إلخ)
        """
        self.config = config
        self.templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # تهيئة بيئة القوالب
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True
        )
    
    def send_email(
        self,
        to_emails: Union[str, List[str]],
        subject: str,
        template_name: str = None,
        template_vars: Dict[str, Any] = None,
        plain_text: str = None,
        html_content: str = None,
        attachments: List[Dict[str, Any]] = None,
        cc_emails: Union[str, List[str]] = None,
        bcc_emails: Union[str, List[str]] = None
    ) -> Tuple[bool, str]:
        """
        إرسال بريد إلكتروني
        
        المعلمات:
            to_emails: قائمة بعناوين البريد الإلكتروني للمستلمين أو عنوان واحد
            subject: عنوان الرسالة
            template_name: اسم ملف القالب (اختياري)
            template_vars: متغيرات القالب (اختياري)
            plain_text: نص عادي للرسالة (إذا لم يتم استخدام قالب)
            html_content: محتوى HTML للرسالة (اختياري)
            attachments: قائمة بالمرفقات [{"filename": "...", "content": b"..."}]
            cc_emails: قائمة بعناوين البريد الإلكتروني للنسخة
            bcc_emails: قائمة بعناوين البريد الإلكتروني للنسخة المخفية
            
        العائد:
            tuple: (النجاح/الفشل، رسالة الخطأ إن وجدت)
        """
        try:
            # التحقق من وجود إعدادات SMTP
            smtp_config = self.config.get('smtp', {})
            if not smtp_config:
                return False, "لم يتم تكوين إعدادات SMTP"
            
            # إنشاء رسالة البريد الإلكتروني
            msg = MIMEMultipart('alternative')
            msg['From'] = smtp_config.get('from_email', 'noreply@example.com')
            msg['Subject'] = subject
            
            # معالجة عناوين البريد الإلكتروني
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            msg['To'] = ', '.join(to_emails)
            
            if cc_emails:
                if isinstance(cc_emails, str):
                    cc_emails = [cc_emails]
                msg['Cc'] = ', '.join(cc_emails)
                to_emails.extend(cc_emails)
            
            if bcc_emails:
                if isinstance(bcc_emails, str):
                    bcc_emails = [bcc_emails]
                msg['Bcc'] = ', '.join(bcc_emails)
                to_emails.extend(bcc_emails)
            
            # معالجة محتوى الرسالة
            if template_name:
                # تحميل القالب وتطبيق المتغيرات
                try:
                    template = self.env.get_template(template_name)
                    html_content = template.render(**(template_vars or {}))
                    
                    # إنشاء نسخة نصية من HTML
                    import re
                    plain_text = re.sub(r'<[^>]+>', '', html_content)
                    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                    
                except Exception as e:
                    logger.error(f"فشل في تحميل أو معالجة القالب: {str(e)}")
                    return False, f"فشل في معالجة قالب البريد الإلكتروني: {str(e)}"
            
            # إضافة النص العادي والـ HTML للرسالة
            if plain_text:
                part1 = MIMEText(plain_text, 'plain', 'utf-8')
                msg.attach(part1)
            
            if html_content:
                part2 = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(part2)
            
            # إضافة المرفقات
            if attachments:
                for attachment in attachments:
                    if 'filename' in attachment and 'content' in attachment:
                        part = MIMEApplication(
                            attachment['content'],
                            Name=attachment['filename']
                        )
                        part['Content-Disposition'] = f'attachment; filename="{attachment["filename"]}"'
                        msg.attach(part)
            
            # إرسال البريد الإلكتروني
            with smtplib.SMTP(
                host=smtp_config.get('host', 'smtp.gmail.com'),
                port=smtp_config.get('port', 587)
            ) as server:
                server.starttls()
                server.login(
                    smtp_config.get('username', ''),
                    smtp_config.get('password', '')
                )
                server.send_message(msg)
            
            logger.info(f"تم إرسال البريد الإلكتروني بنجاح إلى: {', '.join(to_emails)}")
            return True, "تم إرسال البريد الإلكتروني بنجاح"
            
        except Exception as e:
            error_msg = f"فشل في إرسال البريد الإلكتروني: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def send_sms(
        self,
        to_numbers: Union[str, List[str]],
        message: str,
        sender: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        إرسال رسالة نصية
        
        المعلمات:
            to_numbers: قائمة بأرقام الهواتف أو رقم واحد
            message: نص الرسالة
            sender: اسم المرسل (اختياري)
            
        العائد:
            tuple: (النجاح/الفشل، رسالة الخطأ إن وجدت)
        """
        try:
            # التحقق من وجود إعدادات SMS API
            sms_config = self.config.get('sms', {})
            if not sms_config:
                return False, "لم يتم تكوين إعدادات الرسائل النصية"
            
            # الحصول على مفتاح API وبيانات الاعتماد
            api_key = sms_config.get('api_key')
            api_url = sms_config.get('api_url')
            
            if not api_key or not api_url:
                return False, "إعدادات SMS API غير مكتملة"
            
            if isinstance(to_numbers, str):
                to_numbers = [to_numbers]
            
            # إعداد بيانات الطلب
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            
            # إرسال الرسائل
            success_count = 0
            for number in to_numbers:
                # تنسيق الرقم إذا لزم الأمر
                number = str(number).strip()
                if not number.startswith('+'):
                    number = f"+{number}"
                
                # إعداد بيانات الرسالة
                payload = {
                    'to': number,
                    'message': message,
                    'sender': sender or sms_config.get('sender_name', 'MaintenanceSys')
                }
                
                # إرسال الطلب
                response = requests.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                # التحقق من نجاح الإرسال
                if response.status_code == 200:
                    success_count += 1
                else:
                    logger.error(f"فشل في إرسال الرسالة إلى {number}: {response.text}")
            
            if success_count == len(to_numbers):
                msg = f"تم إرسال {success_count} رسالة نصية بنجاح"
                logger.info(msg)
                return True, msg
            elif success_count > 0:
                msg = f"تم إرسال {success_count} من أصل {len(to_numbers)} رسالة نصية بنجاح"
                logger.warning(msg)
                return False, msg
            else:
                return False, "فشل في إرسال أي رسائل نصية"
                
        except Exception as e:
            error_msg = f"فشل في إرسال الرسائل النصية: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def send_maintenance_status_update(
        self,
        job: Dict[str, Any],
        new_status: str,
        customer: Dict[str, Any],
        technician: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        إرسال إشعار بتحديث حالة الصيانة
        
        المعلمات:
            job: بيانات طلب الصيانة
            new_status: الحالة الجديدة
            customer: بيانات العميل
            technician: بيانات الفني (اختياري)
            
        العائد:
            tuple: (النجاح/الفشل، رسالة الخطأ إن وجدت)
        """
        try:
            # تحضير متغيرات القالب
            status_ar = self._get_status_arabic(new_status)
            
            template_vars = {
                'customer_name': customer.get('name', 'السيد/السيدة'),
                'tracking_code': job.get('tracking_code', ''),
                'device_type': job.get('device_type', 'الجهاز'),
                'old_status': self._get_status_arabic(job.get('status')),
                'new_status': status_ar,
                'technician_name': technician.get('name', 'فني الصيانة') if technician else 'فني الصيانة',
                'technician_phone': technician.get('phone', '') if technician else '',
                'update_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'support_phone': self.config.get('support_phone', '123456789'),
                'company_name': self.config.get('company_name', 'مركز الصيانة')
            }
            
            # إرسال البريد الإلكتروني
            email_sent = False
            email_error = ""
            
            if customer.get('email'):
                email_subject = f"تحديث حالة طلب الصيانة #{template_vars['tracking_code']} - {status_ar}"
                
                email_success, email_msg = self.send_email(
                    to_emails=customer['email'],
                    subject=email_subject,
                    template_name='status_update.html',  # يجب إنشاء هذا القالب
                    template_vars=template_vars,
                    plain_text=f"""
                    السيد/السيدة {template_vars['customer_name']}،
                    
                    نود إبلاغكم بأن حالة طلب الصيانة الخاص بكم #{template_vars['tracking_code']} 
                    قد تم تحديثها إلى: {status_ar}
                    
                    لمزيد من المعلومات، يرجى التواصل مع فريق الدعم.
                    
                    مع أطيب التحيات،
                    {template_vars['company_name']}
                    """
                )
                
                email_sent = email_success
                if not email_success:
                    email_error = f"فشل في إرسال البريد الإلكتروني: {email_msg}"
            
            # إرسال رسالة نصية
            sms_sent = False
            sms_error = ""
            
            if customer.get('phone'):
                sms_message = f"عزيزي {template_vars['customer_name']}، تم تحديث حالة طلب الصيانة #{template_vars['tracking_code']} إلى: {status_ar}. {template_vars['company_name']}"
                
                sms_success, sms_msg = self.send_sms(
                    to_numbers=customer['phone'],
                    message=sms_message
                )
                
                sms_sent = sms_success
                if not sms_success:
                    sms_error = f"فشل في إرسال الرسالة النصية: {sms_msg}"
            
            # تجميع النتائج
            if (email_sent or sms_sent):
                success_msg = []
                if email_sent:
                    success_msg.append("تم إرسال البريد الإلكتروني")
                if sms_sent:
                    success_msg.append("تم إرسال الرسالة النصية")
                
                error_msg = []
                if not email_sent and customer.get('email'):
                    error_msg.append(email_error)
                if not sms_sent and customer.get('phone'):
                    error_msg.append(sms_error)
                
                msg = ". ".join(success_msg)
                if error_msg:
                    msg += f" | أخطاء: {" | ".join(error_msg)}"
                
                return True, msg
            else:
                errors = []
                if customer.get('email'):
                    errors.append(email_error)
                if customer.get('phone'):
                    errors.append(sms_error)
                
                return False, " | ".join(errors) if errors else "فشل في إرسال الإشعارات"
                
        except Exception as e:
            error_msg = f"فشل في إرسال إشعار تحديث الحالة: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _get_status_arabic(self, status: str) -> str:
        """تحويل رمز الحالة إلى نص عربي"""
        status_map = {
            'received': 'تم الاستلام',
            'inspection': 'قيد الفحص',
            'approval': 'في انتظار الموافقة',
            'repair': 'قيد الإصلاح',
            'ready': 'جاهز للتسليم',
            'delivered': 'تم التسليم',
            'cancelled': 'ملغي'
        }
        return status_map.get(status, status)
    
    def send_payment_receipt(
        self,
        payment: Dict[str, Any],
        job: Dict[str, Any],
        customer: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        إرسال إيصال الدفع
        
        المعلمات:
            payment: بيانات الدفعة
            job: بيانات طلب الصيانة
            customer: بيانات العميل
            
        العائد:
            tuple: (النجاح/الفشل، رسالة الخطأ إن وجدت)
        """
        try:
            # تحضير متغيرات القالب
            template_vars = {
                'customer_name': customer.get('name', 'السيد/السيدة'),
                'tracking_code': job.get('tracking_code', ''),
                'payment_date': payment.get('created_at', datetime.now()).strftime('%Y-%m-%d %H:%M'),
                'payment_amount': f"{payment.get('amount', 0):.2f} ر.س",
                'payment_method': payment.get('payment_method', 'نقداً'),
                'payment_status': 'مدفوع' if payment.get('status') == 'paid' else 'معلق',
                'company_name': self.config.get('company_name', 'مركز الصيانة'),
                'company_address': self.config.get('company_address', ''),
                'company_phone': self.config.get('support_phone', ''),
                'receipt_number': f"RCPT-{payment.get('id', '')}",
                'device_type': job.get('device_type', 'الجهاز'),
                'device_model': job.get('device_model', 'غير محدد')
            }
            
            # إنشاء محتوى HTML للإيصال
            receipt_html = f"""
            <!DOCTYPE html>
            <html dir="rtl" lang="ar">
            <head>
                <meta charset="UTF-8">
                <title>إيصال دفع - {template_vars['receipt_number']}</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                        border-bottom: 2px solid #eee;
                        padding-bottom: 20px;
                    }}
                    .company-name {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #2c3e50;
                        margin: 0;
                    }}
                    .receipt-title {{
                        font-size: 20px;
                        margin: 10px 0;
                        color: #3498db;
                    }}
                    .receipt-details {{
                        background-color: #f9f9f9;
                        padding: 20px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    .detail-row {{
                        display: flex;
                        margin-bottom: 10px;
                    }}
                    .detail-label {{
                        font-weight: bold;
                        width: 150px;
                        color: #555;
                    }}
                    .detail-value {{
                        flex-grow: 1;
                    }}
                    .footer {{
                        margin-top: 30px;
                        text-align: center;
                        font-size: 14px;
                        color: #777;
                        border-top: 1px solid #eee;
                        padding-top: 20px;
                    }}
                    .thank-you {{
                        font-size: 18px;
                        color: #27ae60;
                        text-align: center;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1 class="company-name">{company_name}</h1>
                    <h2 class="receipt-title">إيصال استلام مبلغ</h2>
                    <p>رقم الإيصال: {receipt_number}</p>
                </div>
                
                <div class="receipt-details">
                    <div class="detail-row">
                        <div class="detail-label">اسم العميل:</div>
                        <div class="detail-value">{customer_name}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">رقم طلب الصيانة:</div>
                        <div class="detail-value">{tracking_code}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">نوع الجهاز:</div>
                        <div class="detail-value">{device_type} {device_model}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">المبلغ المدفوع:</div>
                        <div class="detail-value" style="font-weight: bold; font-size: 18px; color: #27ae60;">{payment_amount}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">طريقة الدفع:</div>
                        <div class="detail-value">{payment_method}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">حالة الدفع:</div>
                        <div class="detail-value">{payment_status}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">تاريخ الدفع:</div>
                        <div class="detail-value">{payment_date}</div>
                    </div>
                </div>
                
                <div class="thank-you">
                    شكراً لثقتكم بنا
                </div>
                
                <div class="footer">
                    <p>{company_name} | {company_address} | هاتف: {company_phone}</p>
                    <p>هذا إيصال إلكتروني صالح كإثبات دفع</p>
                </div>
            </body>
            </html>
            """.format(**template_vars)
            
            # إرسال البريد الإلكتروني مع مرفق PDF (اختياري)
            email_sent = False
            email_error = ""
            
            if customer.get('email'):
                email_subject = f"إيصال دفع - طلب الصيانة #{template_vars['tracking_code']}"
                
                # إنشاء ملف PDF (اختياري)
                pdf_attachment = None
                try:
                    from weasyprint import HTML
                    from io import BytesIO
                    
                    pdf_file = BytesIO()
                    HTML(string=receipt_html).write_pdf(pdf_file)
                    pdf_attachment = {
                        'filename': f"receipt_{template_vars['receipt_number']}.pdf",
                        'content': pdf_file.getvalue()
                    }
                except Exception as e:
                    logger.warning(f"فشل في إنشاء ملف PDF: {str(e)}")
                
                # إرسال البريد الإلكتروني
                email_success, email_msg = self.send_email(
                    to_emails=customer['email'],
                    subject=email_subject,
                    html_content=receipt_html,
                    attachments=[pdf_attachment] if pdf_attachment else None
                )
                
                email_sent = email_success
                if not email_success:
                    email_error = f"فشل في إرسال البريد الإلكتروني: {email_msg}"
            
            # إرسال رسالة نصية
            sms_sent = False
            sms_error = ""
            
            if customer.get('phone'):
                sms_message = f"عزيزي {template_vars['customer_name']}، تم استلام مبلغ {template_vars['payment_amount']} مقابل طلب الصيانة #{template_vars['tracking_code']}. شكراً لثقتكم بنا. {template_vars['company_name']}"
                
                sms_success, sms_msg = self.send_sms(
                    to_numbers=customer['phone'],
                    message=sms_message
                )
                
                sms_sent = sms_success
                if not sms_success:
                    sms_error = f"فشل في إرسال الرسالة النصية: {sms_msg}"
            
            # تجميع النتائج
            if (email_sent or sms_sent):
                success_msg = []
                if email_sent:
                    success_msg.append("تم إرسال إيصال الدفع بالبريد الإلكتروني")
                if sms_sent:
                    success_msg.append("تم إرسال تأكيد الدفع برسالة نصية")
                
                error_msg = []
                if not email_sent and customer.get('email'):
                    error_msg.append(email_error)
                if not sms_sent and customer.get('phone'):
                    error_msg.append(sms_error)
                
                msg = ". ".join(success_msg)
                if error_msg:
                    msg += f" | أخطاء: {" | ".join(error_msg)}"
                
                return True, msg
            else:
                errors = []
                if customer.get('email'):
                    errors.append(email_error)
                if customer.get('phone'):
                    errors.append(sms_error)
                
                return False, " | ".join(errors) if errors else "فشل في إرسال إشعارات الدفع"
                
        except Exception as e:
            error_msg = f"فشل في إرسال إشعار الدفع: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
