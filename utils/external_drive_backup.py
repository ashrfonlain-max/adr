"""
نظام النسخ الاحتياطي إلى USB أو هارد ديسك خارجي
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import platform

class ExternalDriveBackup:
    """نظام النسخ الاحتياطي إلى USB أو هارد ديسك خارجي"""
    
    def __init__(self):
        self.system = platform.system()
        
    def detect_external_drives(self) -> List[Dict[str, Any]]:
        """اكتشاف محركات USB أو الهارد ديسك الخارجية"""
        drives = []
        
        try:
            if self.system == "Windows":
                # Windows: البحث في محركات A-Z
                import string
                for drive_letter in string.ascii_uppercase:
                    drive_path = f"{drive_letter}:\\"
                    if os.path.exists(drive_path):
                        try:
                            # التحقق من أن المحرك قابل للكتابة
                            test_file = Path(drive_path) / "test_write.tmp"
                            try:
                                test_file.write_text("test")
                                test_file.unlink()
                                writable = True
                            except:
                                writable = False
                            
                            # الحصول على معلومات المحرك
                            stat = os.statvfs(drive_path) if hasattr(os, 'statvfs') else None
                            
                            drive_info = {
                                "path": drive_path,
                                "name": f"Drive {drive_letter}",
                                "writable": writable,
                                "exists": True
                            }
                            
                            # محاولة الحصول على اسم المحرك
                            try:
                                import win32api
                                volume_name = win32api.GetVolumeInformation(drive_path)[0]
                                if volume_name:
                                    drive_info["name"] = volume_name
                            except:
                                pass
                            
                            drives.append(drive_info)
                            
                        except Exception as e:
                            continue
            
            elif self.system == "Linux" or self.system == "Darwin":  # Linux or macOS
                # Linux/macOS: البحث في /media أو /Volumes
                mount_points = []
                
                if self.system == "Linux":
                    mount_points = [
                        "/media",
                        "/mnt",
                        "/run/media"
                    ]
                elif self.system == "Darwin":  # macOS
                    mount_points = [
                        "/Volumes"
                    ]
                
                for mount_point in mount_points:
                    if os.path.exists(mount_point):
                        try:
                            for item in os.listdir(mount_point):
                                drive_path = os.path.join(mount_point, item)
                                if os.path.isdir(drive_path) and os.access(drive_path, os.W_OK):
                                    drive_info = {
                                        "path": drive_path,
                                        "name": item,
                                        "writable": True,
                                        "exists": True
                                    }
                                    drives.append(drive_info)
                        except PermissionError:
                            continue
                        except Exception:
                            continue
            
        except Exception as e:
            print(f"خطأ في اكتشاف المحركات: {e}")
        
        return drives
    
    def copy_backup_to_drive(self, backup_file_path: str, target_drive_path: str, create_folder: bool = True) -> Dict[str, Any]:
        """نسخ النسخة الاحتياطية إلى محرك خارجي"""
        try:
            backup_path = Path(backup_file_path)
            if not backup_path.exists():
                return {
                    "success": False,
                    "error": f"ملف النسخة الاحتياطية غير موجود: {backup_file_path}"
                }
            
            target_drive = Path(target_drive_path)
            if not target_drive.exists():
                return {
                    "success": False,
                    "error": f"المسار المستهدف غير موجود: {target_drive_path}"
                }
            
            # التحقق من إمكانية الكتابة
            if not os.access(target_drive, os.W_OK):
                return {
                    "success": False,
                    "error": f"لا يمكن الكتابة على المحرك: {target_drive_path}"
                }
            
            # إنشاء مجلد النسخ الاحتياطي إذا لزم الأمر
            backup_folder_name = "ADR_Maintenance_Backups"
            backup_folder = target_drive / backup_folder_name
            
            if create_folder:
                backup_folder.mkdir(exist_ok=True)
            
            # نسخ الملف
            target_file = backup_folder / backup_path.name
            
            print(f"📁 جاري نسخ النسخة الاحتياطية إلى المحرك الخارجي...")
            print(f"📂 المصدر: {backup_path}")
            print(f"📂 الهدف: {target_file}")
            print(f"📊 الحجم: {backup_path.stat().st_size / (1024*1024):.2f} MB")
            
            shutil.copy2(backup_path, target_file)
            
            # التحقق من نجاح النسخ
            if target_file.exists():
                source_size = backup_path.stat().st_size
                target_size = target_file.stat().st_size
                
                if source_size == target_size:
                    print(f"✅ تم نسخ النسخة الاحتياطية بنجاح!")
                    return {
                        "success": True,
                        "source_path": str(backup_path),
                        "target_path": str(target_file),
                        "size": target_size,
                        "message": f"تم نسخ النسخة الاحتياطية إلى {target_drive_path} بنجاح"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"حجم الملف المنسوخ غير متطابق. المصدر: {source_size} بايت، الهدف: {target_size} بايت"
                    }
            else:
                return {
                    "success": False,
                    "error": "فشل في نسخ الملف"
                }
                
        except PermissionError:
            return {
                "success": False,
                "error": f"لا توجد صلاحيات للكتابة على: {target_drive_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في نسخ الملف: {str(e)}"
            }
    
    def list_backups_on_drive(self, drive_path: str) -> Dict[str, Any]:
        """عرض قائمة النسخ الاحتياطية على محرك خارجي"""
        try:
            drive = Path(drive_path)
            if not drive.exists():
                return {
                    "success": False,
                    "error": f"المسار غير موجود: {drive_path}"
                }
            
            backup_folder = drive / "ADR_Maintenance_Backups"
            if not backup_folder.exists():
                return {
                    "success": True,
                    "backups": [],
                    "count": 0,
                    "message": "لا توجد نسخ احتياطية على هذا المحرك"
                }
            
            backups = []
            for backup_file in backup_folder.glob("*.zip"):
                try:
                    backups.append({
                        "file_name": backup_file.name,
                        "file_path": str(backup_file),
                        "size": backup_file.stat().st_size,
                        "size_mb": round(backup_file.stat().st_size / (1024 * 1024), 2),
                        "created_time": backup_file.stat().st_ctime,
                        "modified_time": backup_file.stat().st_mtime
                    })
                except Exception:
                    continue
            
            # ترتيب حسب تاريخ التعديل (الأحدث أولاً)
            backups.sort(key=lambda x: x["modified_time"], reverse=True)
            
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
    
    def delete_backup_from_drive(self, backup_file_path: str) -> Dict[str, Any]:
        """حذف نسخة احتياطية من محرك خارجي"""
        try:
            backup_path = Path(backup_file_path)
            if not backup_path.exists():
                return {
                    "success": False,
                    "error": f"الملف غير موجود: {backup_file_path}"
                }
            
            backup_path.unlink()
            
            return {
                "success": True,
                "message": "تم حذف النسخة الاحتياطية بنجاح"
            }
            
        except PermissionError:
            return {
                "success": False,
                "error": "لا توجد صلاحيات لحذف الملف"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في حذف الملف: {str(e)}"
            }
    
    def get_drive_space_info(self, drive_path: str) -> Dict[str, Any]:
        """الحصول على معلومات المساحة المتاحة على المحرك"""
        try:
            drive = Path(drive_path)
            if not drive.exists():
                return {
                    "success": False,
                    "error": f"المسار غير موجود: {drive_path}"
                }
            
            if self.system == "Windows":
                import shutil
                total, used, free = shutil.disk_usage(drive_path)
            else:
                stat = os.statvfs(drive_path)
                total = stat.f_frsize * stat.f_blocks
                free = stat.f_frsize * stat.f_bavail
                used = total - free
            
            return {
                "success": True,
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
                "free_percent": round((free / total) * 100, 2) if total > 0 else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"خطأ في الحصول على معلومات المساحة: {str(e)}"
            }






