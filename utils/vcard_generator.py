"""
مولد ملفات vCard لحفظ جهات الاتصال
"""

import os
from typing import Optional
import qrcode
from io import BytesIO

class VCardGenerator:
    """مولد ملفات vCard لحفظ جهات الاتصال في الهاتف"""
    
    def __init__(self, output_dir: str = "contacts"):
        """
        تهيئة مولد vCard
        
        Args:
            output_dir: المجلد الذي سيتم حفظ الملفات فيه
        """
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def create_vcard(
        self, 
        name: str, 
        phone: str, 
        email: Optional[str] = None,
        address: Optional[str] = None,
        company: str = "ADR ELECTRONICS"
    ) -> str:
        """
        إنشاء ملف vCard
        
        Args:
            name: اسم العميل
            phone: رقم الهاتف
            email: البريد الإلكتروني (اختياري)
            address: العنوان (اختياري)
            company: اسم الشركة
            
        Returns:
            مسار الملف المُنشأ
        """
        # تنظيف رقم الهاتف
        phone_clean = phone.replace(' ', '').replace('-', '').replace('+', '')
        if not phone_clean.startswith('961'):
            if phone_clean.startswith('0'):
                phone_clean = '961' + phone_clean[1:]
            else:
                phone_clean = '961' + phone_clean
        
        # إنشاء محتوى vCard
        vcard_content = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
N:{name};;;
TEL;TYPE=CELL:+{phone_clean}
ORG:{company}
"""
        
        if email:
            vcard_content += f"EMAIL:{email}\n"
        
        if address:
            vcard_content += f"ADR:;;{address};;;;\n"
        
        vcard_content += "END:VCARD\n"
        
        # حفظ الملف
        filename = f"{name.replace(' ', '_')}_{phone_clean[:10]}.vcf"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(vcard_content)
        
        return filepath
    
    def create_qr_code(self, vcard_path: str) -> str:
        """
        إنشاء QR Code من ملف vCard
        
        Args:
            vcard_path: مسار ملف vCard
            
        Returns:
            مسار صورة QR Code
        """
        # قراءة محتوى vCard
        with open(vcard_path, 'r', encoding='utf-8') as f:
            vcard_content = f.read()
        
        # إنشاء QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(vcard_content)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # حفظ الصورة
        qr_filename = vcard_path.replace('.vcf', '_qr.png')
        img.save(qr_filename)
        
        return qr_filename
    
    
    def open_in_system(self, vcard_path: str):
        """
        فتح ملف vCard في التطبيق الافتراضي (جهات الاتصال)
        
        Args:
            vcard_path: مسار ملف vCard
        """
        import platform
        import subprocess
        
        system = platform.system()
        
        try:
            if system == 'Windows':
                os.startfile(vcard_path)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', vcard_path])
            else:  # Linux
                subprocess.run(['xdg-open', vcard_path])
            return True
        except Exception as e:
            print(f"خطأ في فتح الملف: {e}")
            return False


