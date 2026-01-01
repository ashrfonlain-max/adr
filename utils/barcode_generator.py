"""
وحدة إنشاء الباركود لطلبات الصيانة
"""

import os
from barcode import Code128
from barcode.writer import ImageWriter
from datetime import datetime
from typing import Optional

class BarcodeGenerator:
    """فئة لإنشاء ورموز الباركود لطلبات الصيانة"""
    
    def __init__(self, output_dir: str = "barcodes"):
        """تهيئة مولد الباركود مع مجلد الإخراج"""
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_barcode(self, tracking_code: str, barcode_data: Optional[str] = None) -> str:
        """
        إنشاء صورة باركود لرقم التتبع
        
        المعلمات:
            tracking_code: رقم تتبع طلب الصيانة
            barcode_data: بيانات إضافية للباركود (اختياري)
            
        العائد:
            مسار ملف صورة الباركود
        """
        try:
            # استخدام رقم التتبع كبيانات الباركود إذا لم يتم توفير بيانات إضافية
            code_data = barcode_data or tracking_code
            
            # إنشاء كائن الباركود من النوع Code128
            barcode = Code128(code_data, writer=ImageWriter())
            
            # إعداد خيارات الصورة
            options = {
                'module_width': 0.4,  # عرض الوحدة النمطية
                'module_height': 15.0,  # ارتفاع الوحدة النمطية
                'font_size': 12,  # حجم الخط
                'text_distance': 2.0,  # المسافة بين النص والباركود
                'quiet_zone': 2.0,  # المنطقة الهادئة حول الباركود
                'write_text': True,  # عرض النص أسفل الباركود
                'text': f"{tracking_code}"  # النص المعروض
            }
            
            # إنشاء اسم ملف فريد باستخدام الطابع الزمني
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"barcode_{tracking_code}_{timestamp}"
            filepath = os.path.join(self.output_dir, filename)
            
            # حفظ صورة الباركود
            barcode.save(filepath, options)
            
            return f"{filepath}.png"
            
        except Exception as e:
            raise Exception(f"فشل في إنشاء الباركود: {str(e)}")
    
    def generate_barcode_with_logo(self, tracking_code: str, logo_path: str, barcode_data: Optional[str] = None) -> str:
        """
        إنشاء صورة باركود مع شعار
        
        المعلمات:
            tracking_code: رقم تتبع طلب الصيانة
            logo_path: مسار ملف الشعار
            barcode_data: بيانات إضافية للباركود (اختياري)
            
        العائد:
            مسار ملف صورة الباركود
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap
            
            # إنشاء الباركود الأساسي أولاً
            barcode_path = self.generate_barcode(tracking_code, barcode_data)
            
            # فتح صورة الباركود
            barcode_img = Image.open(barcode_path)
            barcode_width, barcode_height = barcode_img.size
            
            # فتح صورة الشعار
            logo_img = Image.open(logo_path)
            
            # تغيير حجم الشعار ليتناسب مع عرض الباركود مع الحفاظ على النسبة
            logo_ratio = logo_img.width / logo_img.height
            new_logo_height = int(barcode_height * 0.3)  # ارتفاع الشعار 30% من ارتفاع الباركود
            new_logo_width = int(new_logo_height * logo_ratio)
            logo_img = logo_img.resize((new_logo_width, new_logo_height), Image.Resampling.LANCZOS)
            
            # إنشاء صورة جديدة تجمع بين الباركود والشعار
            result_width = barcode_width
            result_height = barcode_height + new_logo_height + 10  # إضافة هامش 10 بكسل
            
            result = Image.new('RGB', (result_width, result_height), 'white')
            
            # لصق الشعار في الأعلى
            logo_position = ((result_width - new_logo_width) // 2, 5)
            result.paste(logo_img, logo_position)
            
            # لصق الباركود أسفل الشعار
            barcode_position = (0, new_logo_height + 5)
            result.paste(barcode_img, barcode_position)
            
            # إضافة نص إضافي إذا لزم الأمر
            if barcode_data:
                draw = ImageDraw.Draw(result)
                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except:
                    font = ImageFont.load_default()
                
                # تقسيم النص إذا كان طويلاً
                lines = textwrap.wrap(barcode_data, width=30)
                y_position = barcode_position[1] + barcode_height + 5
                
                for line in lines:
                    text_width = draw.textlength(line, font=font)
                    text_position = ((result_width - text_width) // 2, y_position)
                    draw.text(text_position, line, fill="black", font=font)
                    y_position += 20  # المسافة بين الأسطر
            
            # حفظ الصورة النهائية
            result_path = f"{barcode_path}_with_logo.png"
            result.save(result_path)
            
            # حذف ملف الباركود المؤقت
            os.remove(barcode_path)
            
            return result_path
            
        except Exception as e:
            # في حالة حدوث خطأ، نرجع ملف الباركود العادي إذا كان موجوداً
            if os.path.exists(barcode_path):
                return barcode_path
            raise Exception(f"فشل في إنشاء الباركود مع الشعار: {str(e)}")
    
    def generate_qr_code(self, data: str, size: int = 10) -> str:
        """
        إنشاء رمز استجابة سريعة (QR Code)
        
        المعلمات:
            data: البيانات المشفرة في QR Code
            size: حجم الصورة (1-40)
            
        العائد:
            مسار ملف صورة QR Code
        """
        try:
            import qrcode
            
            # إنشاء كائن QR Code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=size,
                border=4,
            )
            
            qr.add_data(data)
            qr.make(fit=True)
            
            # إنشاء صورة QR Code
            img = qr.make_image(fill_color="black", back_color="white")
            
            # حفظ الصورة
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"qrcode_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            
            img.save(filepath)
            
            return filepath
            
        except Exception as e:
            raise Exception(f"فشل في إنشاء QR Code: {str(e)}")
    
    def print_barcode(self, barcode_path: str, printer_name: Optional[str] = None) -> bool:
        """
        طباعة صورة الباركود على الطابعة
        
        المعلمات:
            barcode_path: مسار ملف صورة الباركود
            printer_name: اسم الطابعة (اختياري، إذا لم يتم تحديده سيتم استخدام الطابعة الافتراضية)
            
        العائد:
            bool: نجاح أو فشل العملية
        """
        try:
            import win32print
            import win32ui
            import win32con
            import win32api
            from PIL import Image, ImageWin
            
            # فتح صورة الباركود
            barcode_image = Image.open(barcode_path)
            
            # الحصول على أبعاد الصورة
            width, height = barcode_image.size
            
            # الحصول على معلومات الطابعة
            if printer_name:
                printer = win32print.OpenPrinter(printer_name)
            else:
                printer = win32print.GetDefaultPrinter()
                printer = win32print.OpenPrinter(printer)
            
            try:
                # بدء مستند طباعة
                hprinter = win32ui.CreateDC()
                hprinter.CreatePrinterDC(printer_name)
                hprinter.StartDoc('Barcode Print')
                hprinter.StartPage()
                
                # تحويل الصورة إلى تنسيق يمكن طباعته
                dib = ImageWin.Dib(barcode_image)
                
                # حساب أبعاد الطباعة (A4: 8.27 × 11.69 بوصة، 300 نقطة في البوصة)
                dpi = 300
                page_width = 8.27 * dpi  # عرض الصفحة بالبكسل
                page_height = 11.69 * dpi  # ارتفاع الصفحة بالبكسل
                
                # حساب الموقع المركزي للصفحة
                x = (page_width - width) // 2
                y = (page_height - height) // 2
                
                # رسم الصورة على صفحة الطباعة
                dib.draw(hprinter.GetHandleOutput(), (x, y, x + width, y + height))
                
                # إنهاء الطباعة
                hprinter.EndPage()
                hprinter.EndDoc()
                
                return True
                
            finally:
                # إغلاق مقبض الطابعة
                win32print.ClosePrinter(printer)
                
        except Exception as e:
            print(f"خطأ في الطباعة: {str(e)}")
            return False
            
        finally:
            # حذف ملف الباركود المؤقت
            try:
                os.remove(barcode_path)
            except:
                pass
