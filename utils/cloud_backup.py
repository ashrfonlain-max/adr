"""
نظام النسخ الاحتياطي إلى Google Drive
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    from io import FileIO
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    MediaIoBaseDownload = None

import config

# نطاقات الصلاحيات المطلوبة
SCOPES = ['https://www.googleapis.com/auth/drive.file']


class GoogleDriveBackup:
    """نظام النسخ الاحتياطي إلى Google Drive"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self.token_file = Path("backups") / "google_drive_token.json"
        self.credentials_file = Path("backups") / "google_drive_credentials.json"
        self.backup_folder_name = "ADR_Maintenance_Backups"
        self.backup_folder_id = None
        
    def is_available(self) -> bool:
        """التحقق من توفر Google Drive API"""
        return GOOGLE_DRIVE_AVAILABLE
    
    def authenticate(self) -> Dict[str, Any]:
        """المصادقة مع Google Drive"""
        if not self.is_available():
            return {
                "success": False,
                "error": "مكتبة Google Drive API غير مثبتة. قم بتثبيتها: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            }
        
        try:
            creds = None
            
            # محاولة تحميل بيانات الاعتماد المحفوظة
            if self.token_file.exists():
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            
            # إذا لم تكن هناك بيانات اعتماد صالحة، اطلب من المستخدم المصادقة
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # تحديث بيانات الاعتماد المنتهية
                    creds.refresh(Request())
                else:
                    # طلب مصادقة جديدة
                    if not self.credentials_file.exists():
                        return {
                            "success": False,
                            "error": f"ملف بيانات الاعتماد غير موجود: {self.credentials_file}\nيرجى تحميل ملف credentials.json من Google Cloud Console وحفظه في: {self.credentials_file}"
                        }
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # حفظ بيانات الاعتماد للمرة القادمة
                self.token_file.parent.mkdir(exist_ok=True)
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            self.credentials = creds
            self.service = build('drive', 'v3', credentials=creds)
            
            # إنشاء أو العثور على مجلد النسخ الاحتياطي
            self.backup_folder_id = self._get_or_create_backup_folder()
            
            return {
                "success": True,
                "message": "تم المصادقة مع Google Drive بنجاح"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في المصادقة: {str(e)}"
            }
    
    def _get_or_create_backup_folder(self) -> Optional[str]:
        """الحصول على أو إنشاء مجلد النسخ الاحتياطي"""
        try:
            # البحث عن المجلد
            results = self.service.files().list(
                q=f"name='{self.backup_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                # المجلد موجود
                return items[0]['id']
            else:
                # إنشاء مجلد جديد
                file_metadata = {
                    'name': self.backup_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                return folder.get('id')
                
        except Exception as e:
            print(f"خطأ في إنشاء/البحث عن مجلد النسخ الاحتياطي: {e}")
            return None
    
    def upload_backup(self, backup_file_path: str) -> Dict[str, Any]:
        """رفع نسخة احتياطية إلى Google Drive"""
        try:
            if not self.service:
                auth_result = self.authenticate()
                if not auth_result.get("success"):
                    return auth_result
            
            if not self.backup_folder_id:
                self.backup_folder_id = self._get_or_create_backup_folder()
                if not self.backup_folder_id:
                    return {
                        "success": False,
                        "error": "فشل في إنشاء أو العثور على مجلد النسخ الاحتياطي"
                    }
            
            backup_path = Path(backup_file_path)
            if not backup_path.exists():
                return {
                    "success": False,
                    "error": f"ملف النسخة الاحتياطية غير موجود: {backup_file_path}"
                }
            
            # معلومات الملف
            file_metadata = {
                'name': backup_path.name,
                'parents': [self.backup_folder_id]
            }
            
            # رفع الملف
            media = MediaFileUpload(
                str(backup_path),
                mimetype='application/zip',
                resumable=True
            )
            
            print(f"📤 جاري رفع النسخة الاحتياطية إلى Google Drive...")
            print(f"📁 الملف: {backup_path.name}")
            print(f"📊 الحجم: {backup_path.stat().st_size / (1024*1024):.2f} MB")
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size'
            ).execute()
            
            print(f"✅ تم رفع النسخة الاحتياطية بنجاح!")
            print(f"🆔 معرف الملف: {file.get('id')}")
            
            return {
                "success": True,
                "file_id": file.get('id'),
                "file_name": file.get('name'),
                "message": "تم رفع النسخة الاحتياطية إلى Google Drive بنجاح"
            }
            
        except HttpError as e:
            error_details = json.loads(e.content.decode('utf-8'))
            error_message = error_details.get('error', {}).get('message', str(e))
            return {
                "success": False,
                "error": f"خطأ في رفع الملف: {error_message}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ غير متوقع: {str(e)}"
            }
    
    def list_backups(self) -> Dict[str, Any]:
        """عرض قائمة النسخ الاحتياطية على Google Drive"""
        try:
            if not self.service:
                auth_result = self.authenticate()
                if not auth_result.get("success"):
                    return auth_result
            
            if not self.backup_folder_id:
                self.backup_folder_id = self._get_or_create_backup_folder()
            
            # البحث عن جميع ملفات ZIP في مجلد النسخ الاحتياطي
            query = f"'{self.backup_folder_id}' in parents and mimeType='application/zip' and trashed=false"
            results = self.service.files().list(
                q=query,
                fields='files(id, name, size, createdTime, modifiedTime)',
                orderBy='createdTime desc'
            ).execute()
            
            items = results.get('files', [])
            
            backups = []
            for item in items:
                backups.append({
                    "file_id": item.get('id'),
                    "file_name": item.get('name'),
                    "size": int(item.get('size', 0)),
                    "size_mb": round(int(item.get('size', 0)) / (1024 * 1024), 2),
                    "created_time": item.get('createdTime'),
                    "modified_time": item.get('modifiedTime')
                })
            
            return {
                "success": True,
                "backups": backups,
                "count": len(backups)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في عرض النسخ الاحتياطية: {str(e)}"
            }
    
    def delete_backup(self, file_id: str) -> Dict[str, Any]:
        """حذف نسخة احتياطية من Google Drive"""
        try:
            if not self.service:
                auth_result = self.authenticate()
                if not auth_result.get("success"):
                    return auth_result
            
            self.service.files().delete(fileId=file_id).execute()
            
            return {
                "success": True,
                "message": "تم حذف النسخة الاحتياطية بنجاح"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في حذف النسخة الاحتياطية: {str(e)}"
            }
    
    def download_backup(self, file_id: str, download_path: str) -> Dict[str, Any]:
        """تحميل نسخة احتياطية من Google Drive"""
        try:
            if not self.is_available() or MediaIoBaseDownload is None:
                return {
                    "success": False,
                    "error": "مكتبة Google Drive API غير متاحة"
                }
            
            if not self.service:
                auth_result = self.authenticate()
                if not auth_result.get("success"):
                    return auth_result
            
            request = self.service.files().get_media(fileId=file_id)
            
            download_path = Path(download_path)
            download_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(download_path, 'wb') as f:
                downloader = MediaIoBaseDownload(FileIO(download_path, 'wb'), request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    if status:
                        print(f"📥 التقدم: {int(status.progress() * 100)}%")
            
            return {
                "success": True,
                "download_path": str(download_path),
                "message": "تم تحميل النسخة الاحتياطية بنجاح"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في تحميل النسخة الاحتياطية: {str(e)}"
            }
    
    def get_account_info(self) -> Dict[str, Any]:
        """الحصول على معلومات حساب Google Drive المستخدم"""
        try:
            if not self.is_available():
                return {
                    "success": False,
                    "error": "مكتبة Google Drive API غير متاحة"
                }
            
            # محاولة تحميل معلومات من ملف token
            if self.token_file.exists():
                try:
                    with open(self.token_file, 'r') as f:
                        token_data = json.load(f)
                        # محاولة استخراج معلومات الحساب من token
                        if 'client_id' in token_data:
                            # هذه معلومات Client ID وليست معلومات الحساب
                            pass
                except:
                    pass
            
            # محاولة الحصول على معلومات الحساب من API
            if not self.service:
                auth_result = self.authenticate()
                if not auth_result.get("success"):
                    # إذا فشلت المصادقة، نحاول قراءة معلومات من token فقط
                    if self.token_file.exists():
                        try:
                            with open(self.token_file, 'r') as f:
                                token_data = json.load(f)
                                return {
                                    "success": True,
                                    "account_email": token_data.get("token", {}).get("id_token", ""),
                                    "token_saved": True,
                                    "note": "تم العثور على رمز مصادقة محفوظ. للعثور على البريد الإلكتروني، يرجى المصادقة أولاً."
                                }
                        except:
                            pass
                    return {
                        "success": False,
                        "error": "يجب إجراء المصادقة أولاً"
                    }
            
            # محاولة الحصول على معلومات المستخدم من Google Drive API
            try:
                # استخدام People API للحصول على معلومات الحساب
                # لكن هذا يتطلب تفعيل People API، لذا سنستخدم طريقة بديلة
                user_info = self.service.about().get(fields='user').execute()
                user_email = user_info.get('user', {}).get('emailAddress', 'غير متاح')
                
                return {
                    "success": True,
                    "account_email": user_email,
                    "display_name": user_info.get('user', {}).get('displayName', 'غير متاح'),
                    "token_saved": self.token_file.exists(),
                    "backup_folder": self.backup_folder_name
                }
            except:
                # إذا فشل، نعيد معلومات من token
                if self.token_file.exists():
                    return {
                        "success": True,
                        "account_email": "غير متاح (يتم تخزينه في رمز المصادقة)",
                        "token_saved": True,
                        "backup_folder": self.backup_folder_name,
                        "note": "للاطلاع على البريد الإلكتروني، افتح Google Drive على الويب وتحقق من المجلد: " + self.backup_folder_name
                    }
                else:
                    return {
                        "success": False,
                        "error": "لا توجد معلومات حساب متاحة. يرجى إجراء المصادقة أولاً."
                    }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في الحصول على معلومات الحساب: {str(e)}"
            }

