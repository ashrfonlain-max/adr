"""
نظام النسخ الاحتياطي الشامل لنظام إدارة الصيانة
"""

import os
import shutil
import sqlite3
import zipfile
import json
from datetime import datetime
from pathlib import Path
import subprocess
import hashlib
from typing import List, Dict, Any, Optional
import config

# استيراد أنظمة النسخ الاحتياطي الإضافية
try:
    from utils.cloud_backup import GoogleDriveBackup
    CLOUD_BACKUP_AVAILABLE = True
except ImportError:
    CLOUD_BACKUP_AVAILABLE = False

try:
    from utils.external_drive_backup import ExternalDriveBackup
    EXTERNAL_DRIVE_BACKUP_AVAILABLE = True
except ImportError:
    EXTERNAL_DRIVE_BACKUP_AVAILABLE = False

class BackupSystem:
    """نظام النسخ الاحتياطي الشامل"""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # تهيئة أنظمة النسخ الاحتياطي الإضافية
        self.google_drive = GoogleDriveBackup() if CLOUD_BACKUP_AVAILABLE else None
        self.external_drive = ExternalDriveBackup() if EXTERNAL_DRIVE_BACKUP_AVAILABLE else None
        
    def create_full_backup(self) -> Dict[str, Any]:
        """إنشاء نسخة احتياطية شاملة للنظام"""
        try:
            print("🔄 بدء إنشاء النسخة الاحتياطية...")
            
            backup_info = {
                "timestamp": self.timestamp,
                "backup_type": "full",
                "files": [],
                "database": {},
                "system_info": self._get_system_info(),
                "checksums": {}
            }
            
            # 1. نسخ احتياطي لقاعدة البيانات
            print("📊 نسخ قاعدة البيانات...")
            db_backup = self._backup_database()
            if "error" in db_backup:
                print(f"⚠️ تحذير في نسخ قاعدة البيانات: {db_backup['error']}")
            backup_info["database"] = db_backup
            
            # 2. نسخ احتياطي لجميع الملفات
            print("📁 نسخ ملفات النظام...")
            files_backup = self._backup_files()
            if files_backup and "error" in files_backup[0]:
                print(f"⚠️ تحذير في نسخ الملفات: {files_backup[0]['error']}")
            backup_info["files"] = files_backup
            
            # 3. إنشاء ملف معلومات النسخة الاحتياطية
            print("📋 إنشاء ملف المعلومات...")
            self._create_backup_info(backup_info)
            
            # 4. ضغط النسخة الاحتياطية
            print("🗜️ ضغط النسخة الاحتياطية...")
            compressed_backup = self._compress_backup()
            
            backup_size = self._get_file_size(compressed_backup)
            print(f"✅ تم إنشاء النسخة الاحتياطية بنجاح! الحجم: {backup_size / (1024*1024):.2f} MB")
            
            result = {
                "success": True,
                "backup_path": str(compressed_backup),
                "backup_info": backup_info,
                "size": backup_size
            }
            
            # النسخ التلقائي إلى Google Drive و USB (إذا كان مفعلاً)
            self._auto_copy_to_cloud_and_external(compressed_backup)
            
            return result
            
        except Exception as e:
            print(f"❌ خطأ في إنشاء النسخة الاحتياطية: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _backup_database(self) -> Dict[str, Any]:
        """نسخ احتياطي لقاعدة البيانات"""
        try:
            # مسار قاعدة البيانات
            db_path = config.DATABASE_URL.replace('sqlite:///', '')
            
            if not os.path.exists(db_path):
                raise FileNotFoundError(f"قاعدة البيانات غير موجودة: {db_path}")
            
            # إنشاء مجلد النسخة الاحتياطية
            backup_db_dir = self.backup_dir / f"database_{self.timestamp}"
            backup_db_dir.mkdir(exist_ok=True)
            
            # نسخ قاعدة البيانات
            backup_db_path = backup_db_dir / "adr_maintenance.db"
            shutil.copy2(db_path, backup_db_path)
            
            # إنشاء نسخة SQL
            sql_backup_path = backup_db_dir / "database_dump.sql"
            self._create_sql_dump(db_path, sql_backup_path)
            
            # حساب checksum
            checksum = self._calculate_checksum(backup_db_path)
            
            return {
                "original_path": db_path,
                "backup_path": str(backup_db_path),
                "sql_dump": str(sql_backup_path),
                "checksum": checksum,
                "size": self._get_file_size(backup_db_path)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _backup_files(self) -> List[Dict[str, Any]]:
        """نسخ احتياطي لجميع ملفات النظام"""
        try:
            # الملفات والمجلدات المهمة
            important_paths = [
                "gui/",
                "services/",
                "database/",
                "utils/",
                "reports/",
                "uploads/",
                "barcodes/",
                "temp/",
                "main.py",
                "run_app.py",
                "config.py",
                "requirements.txt",
                "*.md"
            ]
            
            backup_files_dir = self.backup_dir / f"files_{self.timestamp}"
            backup_files_dir.mkdir(exist_ok=True)
            
            backed_up_files = []
            
            for path_pattern in important_paths:
                if path_pattern.endswith("/"):
                    # مجلد
                    folder_name = path_pattern.rstrip("/")
                    if os.path.exists(folder_name):
                        dest_folder = backup_files_dir / folder_name
                        shutil.copytree(folder_name, dest_folder)
                        backed_up_files.append({
                            "type": "folder",
                            "source": folder_name,
                            "destination": str(dest_folder),
                            "size": self._get_folder_size(dest_folder)
                        })
                else:
                    # ملف
                    if os.path.exists(path_pattern):
                        dest_file = backup_files_dir / path_pattern
                        shutil.copy2(path_pattern, dest_file)
                        backed_up_files.append({
                            "type": "file",
                            "source": path_pattern,
                            "destination": str(dest_file),
                            "size": self._get_file_size(dest_file)
                        })
            
            return backed_up_files
            
        except Exception as e:
            return [{"error": str(e)}]
    
    def _create_sql_dump(self, db_path: str, output_path: str):
        """إنشاء نسخة SQL من قاعدة البيانات"""
        try:
            conn = sqlite3.connect(db_path)
            with open(output_path, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            conn.close()
        except Exception as e:
            print(f"خطأ في إنشاء SQL dump: {e}")
    
    def _compress_backup(self) -> Path:
        """ضغط النسخة الاحتياطية"""
        try:
            backup_name = f"adr_maintenance_backup_{self.timestamp}"
            backup_zip = self.backup_dir / f"{backup_name}.zip"
            
            # إنشاء ملف ZIP مع معالجة أفضل للأخطاء
            with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                # إضافة قاعدة البيانات
                db_backup_dir = self.backup_dir / f"database_{self.timestamp}"
                if db_backup_dir.exists():
                    for file_path in db_backup_dir.rglob("*"):
                        if file_path.is_file():
                            try:
                                arcname = f"database/{file_path.relative_to(db_backup_dir)}"
                                # تحويل المسار إلى string للتأكد من التوافق
                                arcname = str(arcname).replace('\\', '/')
                                zipf.write(str(file_path), arcname)
                            except Exception as e:
                                print(f"خطأ في إضافة ملف قاعدة البيانات {file_path}: {e}")
                
                # إضافة الملفات
                files_backup_dir = self.backup_dir / f"files_{self.timestamp}"
                if files_backup_dir.exists():
                    for file_path in files_backup_dir.rglob("*"):
                        if file_path.is_file():
                            try:
                                arcname = f"files/{file_path.relative_to(files_backup_dir)}"
                                # تحويل المسار إلى string للتأكد من التوافق
                                arcname = str(arcname).replace('\\', '/')
                                zipf.write(str(file_path), arcname)
                            except Exception as e:
                                print(f"خطأ في إضافة ملف النظام {file_path}: {e}")
                
                # إضافة ملف معلومات النسخة الاحتياطية
                info_file = self.backup_dir / f"backup_info_{self.timestamp}.json"
                if info_file.exists():
                    try:
                        zipf.write(str(info_file), "backup_info.json")
                    except Exception as e:
                        print(f"خطأ في إضافة ملف المعلومات: {e}")
            
            # التحقق من أن الملف تم إنشاؤه بنجاح
            if not backup_zip.exists():
                raise Exception("فشل في إنشاء ملف النسخة الاحتياطية")
            
            # التحقق من حجم الملف
            if backup_zip.stat().st_size == 0:
                raise Exception("ملف النسخة الاحتياطية فارغ")
            
            # حذف المجلدات المؤقتة
            try:
                if db_backup_dir.exists():
                    shutil.rmtree(db_backup_dir, ignore_errors=True)
                if files_backup_dir.exists():
                    shutil.rmtree(files_backup_dir, ignore_errors=True)
                if info_file.exists():
                    info_file.unlink()
            except Exception as e:
                # تجاهل أخطاء حذف الملفات المؤقتة
                pass
            
            return backup_zip
            
        except Exception as e:
            raise Exception(f"خطأ في ضغط النسخة الاحتياطية: {e}")
    
    def _create_backup_info(self, backup_info: Dict[str, Any]):
        """إنشاء ملف معلومات النسخة الاحتياطية"""
        info_file = self.backup_dir / f"backup_info_{self.timestamp}.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, ensure_ascii=False, indent=2)
    
    def _get_system_info(self) -> Dict[str, Any]:
        """الحصول على معلومات النظام"""
        try:
            import platform
            import sys
            
            return {
                "platform": platform.platform(),
                "python_version": sys.version,
                "architecture": platform.architecture(),
                "processor": platform.processor(),
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """حساب checksum للملف"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            return f"error: {e}"
    
    def _get_file_size(self, file_path: Path) -> int:
        """الحصول على حجم الملف"""
        try:
            return file_path.stat().st_size
        except:
            return 0
    
    def _get_folder_size(self, folder_path: Path) -> int:
        """الحصول على حجم المجلد"""
        try:
            total_size = 0
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except:
            return 0
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """قائمة النسخ الاحتياطية المتاحة"""
        try:
            backups = []
            for backup_file in self.backup_dir.glob("adr_maintenance_backup_*.zip"):
                try:
                    # استخراج المعلومات من اسم الملف
                    name_parts = backup_file.stem.split("_")
                    if len(name_parts) >= 4:
                        timestamp = f"{name_parts[-2]}_{name_parts[-1]}"
                        backup_date = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                        
                        backups.append({
                            "file_name": backup_file.name,
                            "file_path": str(backup_file),
                            "timestamp": timestamp,
                            "date": backup_date.strftime("%Y-%m-%d %H:%M:%S"),
                            "size": self._get_file_size(backup_file),
                            "size_mb": round(self._get_file_size(backup_file) / (1024 * 1024), 2)
                        })
                except Exception as e:
                    print(f"خطأ في معالجة النسخة الاحتياطية {backup_file.name}: {e}")
            
            # ترتيب حسب التاريخ (الأحدث أولاً)
            backups.sort(key=lambda x: x["timestamp"], reverse=True)
            return backups
            
        except Exception as e:
            return [{"error": str(e)}]
    
    def restore_backup(self, backup_path: str, restore_to: str = None) -> Dict[str, Any]:
        """استعادة نسخة احتياطية"""
        try:
            if not os.path.exists(backup_path):
                return {"success": False, "error": "النسخة الاحتياطية غير موجودة"}
            
            # تحديد مجلد الاستعادة
            if restore_to is None:
                restore_to = "restored_system"
            
            restore_dir = Path(restore_to)
            restore_dir.mkdir(exist_ok=True)
            
            # استخراج النسخة الاحتياطية
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(restore_dir)
            
            # نسخ قاعدة البيانات إلى المكان الصحيح
            db_backup_path = restore_dir / "database" / "adr_maintenance.db"
            if db_backup_path.exists():
                # نسخ إلى مجلد النظام الحالي
                current_db_path = config.DATABASE_URL.replace('sqlite:///', '')
                shutil.copy2(db_backup_path, current_db_path)
            
            return {
                "success": True,
                "restore_path": str(restore_dir),
                "database_restored": db_backup_path.exists()
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_automated_backup(self) -> Dict[str, Any]:
        """إنشاء نسخة احتياطية تلقائية"""
        try:
            # إنشاء نسخة احتياطية يومية
            daily_backup = self.create_full_backup()
            
            # حفظ معلومات النسخة الاحتياطية التلقائية
            auto_backup_info = {
                "type": "automated",
                "created_at": datetime.now().isoformat(),
                "backup_info": daily_backup
            }
            
            auto_backup_file = self.backup_dir / f"auto_backup_{self.timestamp}.json"
            with open(auto_backup_file, 'w', encoding='utf-8') as f:
                json.dump(auto_backup_info, f, ensure_ascii=False, indent=2)
            
            return daily_backup
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _auto_copy_to_cloud_and_external(self, backup_file_path: Path):
        """نسخ تلقائي إلى Google Drive و USB (إذا كان مفعلاً)"""
        try:
            # التحقق من الإعدادات
            backup_to_cloud = getattr(config, 'BACKUP_TO_GOOGLE_DRIVE', False)
            backup_to_external = getattr(config, 'BACKUP_TO_EXTERNAL_DRIVE', False)
            external_drive_path = getattr(config, 'EXTERNAL_DRIVE_PATH', None)
            
            # النسخ إلى Google Drive
            if backup_to_cloud and self.google_drive:
                try:
                    print("\n☁️ جاري النسخ إلى Google Drive...")
                    cloud_result = self.google_drive.upload_backup(str(backup_file_path))
                    if cloud_result.get("success"):
                        print(f"✅ {cloud_result.get('message', 'تم النسخ إلى Google Drive')}")
                    else:
                        print(f"⚠️ فشل النسخ إلى Google Drive: {cloud_result.get('error', 'خطأ غير معروف')}")
                except Exception as e:
                    print(f"⚠️ خطأ في النسخ إلى Google Drive: {str(e)}")
            
            # النسخ إلى USB/External Drive
            if backup_to_external and self.external_drive and external_drive_path:
                try:
                    print("\n💾 جاري النسخ إلى المحرك الخارجي...")
                    external_result = self.external_drive.copy_backup_to_drive(
                        str(backup_file_path),
                        external_drive_path
                    )
                    if external_result.get("success"):
                        print(f"✅ {external_result.get('message', 'تم النسخ إلى المحرك الخارجي')}")
                    else:
                        print(f"⚠️ فشل النسخ إلى المحرك الخارجي: {external_result.get('error', 'خطأ غير معروف')}")
                except Exception as e:
                    print(f"⚠️ خطأ في النسخ إلى المحرك الخارجي: {str(e)}")
        
        except Exception as e:
            print(f"⚠️ خطأ في النسخ التلقائي: {str(e)}")
    
    def upload_to_google_drive(self, backup_file_path: str = None) -> Dict[str, Any]:
        """رفع نسخة احتياطية إلى Google Drive"""
        if not self.google_drive:
            return {
                "success": False,
                "error": "نظام Google Drive غير متاح. قم بتثبيت المكتبات المطلوبة."
            }
        
        if backup_file_path is None:
            # البحث عن آخر نسخة احتياطية
            backups = self.list_backups()
            if not backups or backups[0].get("error"):
                return {
                    "success": False,
                    "error": "لا توجد نسخ احتياطية للرفع"
                }
            backup_file_path = backups[0]["file_path"]
        
        return self.google_drive.upload_backup(backup_file_path)
    
    def copy_to_external_drive(self, backup_file_path: str = None, drive_path: str = None) -> Dict[str, Any]:
        """نسخ نسخة احتياطية إلى محرك خارجي"""
        if not self.external_drive:
            return {
                "success": False,
                "error": "نظام المحركات الخارجية غير متاح"
            }
        
        if backup_file_path is None:
            # البحث عن آخر نسخة احتياطية
            backups = self.list_backups()
            if not backups or backups[0].get("error"):
                return {
                    "success": False,
                    "error": "لا توجد نسخ احتياطية للنسخ"
                }
            backup_file_path = backups[0]["file_path"]
        
        if drive_path is None:
            # اكتشاف المحركات المتاحة
            drives = self.external_drive.detect_external_drives()
            if not drives:
                return {
                    "success": False,
                    "error": "لا توجد محركات خارجية متاحة"
                }
            # استخدام أول محرك قابل للكتابة
            writable_drives = [d for d in drives if d.get("writable")]
            if not writable_drives:
                return {
                    "success": False,
                    "error": "لا توجد محركات قابلة للكتابة"
                }
            drive_path = writable_drives[0]["path"]
        
        return self.external_drive.copy_backup_to_drive(backup_file_path, drive_path)
    
    def detect_external_drives(self) -> List[Dict[str, Any]]:
        """اكتشاف المحركات الخارجية المتاحة"""
        if not self.external_drive:
            return []
        return self.external_drive.detect_external_drives()
    
    def list_google_drive_backups(self) -> Dict[str, Any]:
        """عرض قائمة النسخ الاحتياطية على Google Drive"""
        if not self.google_drive:
            return {
                "success": False,
                "error": "نظام Google Drive غير متاح"
            }
        return self.google_drive.list_backups()
    
    def get_google_drive_account_info(self) -> Dict[str, Any]:
        """الحصول على معلومات حساب Google Drive المستخدم"""
        if not self.google_drive:
            return {
                "success": False,
                "error": "نظام Google Drive غير متاح"
            }
        return self.google_drive.get_account_info()
    
    def list_external_drive_backups(self, drive_path: str) -> Dict[str, Any]:
        """عرض قائمة النسخ الاحتياطية على محرك خارجي"""
        if not self.external_drive:
            return {
                "success": False,
                "error": "نظام المحركات الخارجية غير متاح"
            }
        return self.external_drive.list_backups_on_drive(drive_path)
    
    def cleanup_old_backups(self, keep_days: int = 30) -> Dict[str, Any]:
        """تنظيف النسخ الاحتياطية القديمة"""
        try:
            cutoff_date = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
            deleted_count = 0
            freed_space = 0
            
            for backup_file in self.backup_dir.glob("adr_maintenance_backup_*.zip"):
                if backup_file.stat().st_mtime < cutoff_date:
                    file_size = backup_file.stat().st_size
                    backup_file.unlink()
                    deleted_count += 1
                    freed_space += file_size
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "freed_space_mb": round(freed_space / (1024 * 1024), 2)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
