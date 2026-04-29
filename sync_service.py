"""
Sync Service - مزامنة البيانات بين Supabase و Convex
يقوم بمزامنة البيانات في الاتجاهين للحفاظ على تحديث كلا القاعدتين
"""

import os
import logging
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from supabase_client import supabase

logger = logging.getLogger(__name__)


class SyncService:
    """خدمة المزامنة بين Supabase و Convex"""

    def __init__(self):
        self.convex_url = os.environ.get("CONVEX_DEPLOYMENT_URL")
        self.convex_key = os.environ.get("CONVEX_DEPLOYMENT_KEY")
        self.enabled = bool(self.convex_url and self.convex_key)
        
        if self.enabled:
            self.base_url = f"{self.convex_url}/api/run"
            logger.info("Sync Service: مفعّل")
        else:
            logger.warning("Sync Service: معطّل - متغيرات Convex غير موجودة")

    def _make_convex_request(self, function_name: str, args: Dict[str, Any] = None) -> Optional[Any]:
        """إرسال طلب إلى Convex"""
        if not self.enabled:
            return None

        try:
            # Convex HTTP API format - function name in URL path
            url = f"{self.convex_url}/api/run/botFunctions/{function_name}"
            # Use Convex prefix for dev/admin keys (not Bearer)
            headers = {
                "Authorization": f"Convex {self.convex_key}",
                "Content-Type": "application/json",
            }
            payload = {"args": args or {}}

            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Convex error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Convex request error: {e}")
            return None

    # ============= مزامنة المستخدمين =============

    def sync_user_to_convex(self, user_id: int, username: str = None, first_name: str = "") -> bool:
        """مزامنة مستخدم من Supabase إلى Convex"""
        if not self.enabled:
            return False

        result = self._make_convex_request("upsertUser", {
            "id": user_id,
            "username": username,
            "first_name": first_name or "",
        })
        return result is not None

    def sync_all_users_to_convex(self) -> Dict[str, int]:
        """مزامنة جميع المستخدمين إلى Convex"""
        if not self.enabled:
            return {"synced": 0, "failed": 0}

        try:
            # جلب جميع المستخدمين من Supabase
            resp = supabase.table("users").select("*").execute()
            users = resp.data or []
            
            synced = 0
            failed = 0

            for user in users:
                if self.sync_user_to_convex(
                    user["id"],
                    user.get("username"),
                    user.get("first_name", "")
                ):
                    synced += 1
                else:
                    failed += 1

            logger.info(f"Synced {synced} users to Convex, {failed} failed")
            return {"synced": synced, "failed": failed}
        except Exception as e:
            logger.error(f"Error syncing users: {e}")
            return {"synced": 0, "failed": 0}

    # ============= مزامنة الأدمن =============

    def sync_admin_to_convex(self, admin_data: Dict) -> bool:
        """مزامنة أدمن إلى Convex"""
        if not self.enabled:
            return False

        # نحتاج إضافة دالة upsertAdmin في Convex
        return self._make_convex_request("upsertAdmin", {
            "id": admin_data["id"],
            "username": admin_data.get("username"),
            "first_name": admin_data.get("first_name"),
            "manage_subjects": admin_data.get("manage_subjects", False),
            "delete_files": admin_data.get("delete_files", False),
            "upload_files": admin_data.get("upload_files", False),
            "broadcast": admin_data.get("broadcast", False),
            "manage_admins": admin_data.get("manage_admins", False),
            "view_users": admin_data.get("view_users", False),
            "view_activity": admin_data.get("view_activity", False),
        }) is not None

    def sync_all_admins_to_convex(self) -> Dict[str, int]:
        """مزامنة جميع الأدمن إلى Convex"""
        if not self.enabled:
            return {"synced": 0, "failed": 0}

        try:
            resp = supabase.table("admins").select("*").execute()
            admins = resp.data or []

            synced = 0
            failed = 0

            for admin in admins:
                if self.sync_admin_to_convex(admin):
                    synced += 1
                else:
                    failed += 1

            return {"synced": synced, "failed": failed}
        except Exception as e:
            logger.error(f"Error syncing admins: {e}")
            return {"synced": 0, "failed": 0}

    # ============= مزامنة التصنيفات والمواد =============

    def sync_category_to_convex(self, category_data: Dict) -> bool:
        """مزامنة تصنيف إلى Convex"""
        if not self.enabled:
            return False

        return self._make_convex_request("upsertCategory", {
            "name": category_data["name"],
            "sort_order": category_data.get("sort_order", 0),
            "supabase_id": category_data["id"],
        }) is not None

    def sync_subject_to_convex(self, subject_data: Dict) -> bool:
        """مزامنة مادة إلى Convex"""
        if not self.enabled:
            return False

        return self._make_convex_request("upsertSubject", {
            "name": subject_data["name"],
            "category_id": subject_data.get("category_id"),
            "supabase_id": subject_data["id"],
        }) is not None

    def sync_all_categories_and_subjects(self) -> Dict[str, int]:
        """مزامنة جميع التصنيفات والمواد"""
        if not self.enabled:
            return {"categories": 0, "subjects": 0}

        categories_synced = 0
        subjects_synced = 0

        try:
            # مزامنة التصنيفات
            resp = supabase.table("categories").select("*").execute()
            categories = resp.data or []
            for cat in categories:
                if self.sync_category_to_convex(cat):
                    categories_synced += 1

            # مزامنة المواد
            resp = supabase.table("subjects").select("*").execute()
            subjects = resp.data or []
            for subj in subjects:
                if self.sync_subject_to_convex(subj):
                    subjects_synced += 1

            return {"categories": categories_synced, "subjects": subjects_synced}
        except Exception as e:
            logger.error(f"Error syncing categories/subjects: {e}")
            return {"categories": categories_synced, "subjects": subjects_synced}

    # ============= مزامنة الملفات =============

    def sync_file_to_convex(self, file_data: Dict) -> bool:
        """مزامنة ملف إلى Convex"""
        if not self.enabled:
            return False

        return self._make_convex_request("upsertFile", {
            "name": file_data["name"],
            "file_id": file_data["file_id"],
            "file_type": file_data["file_type"],
            "subject_id": file_data.get("subject_id"),
            "message_id": file_data.get("message_id"),
            "file_size": file_data.get("file_size"),
            "supabase_id": file_data["id"],
        }) is not None

    def sync_all_files_to_convex(self) -> Dict[str, int]:
        """مزامنة جميع الملفات"""
        if not self.enabled:
            return {"synced": 0, "failed": 0}

        try:
            resp = supabase.table("files").select("*").execute()
            files = resp.data or []

            synced = 0
            failed = 0

            for file in files:
                if self.sync_file_to_convex(file):
                    synced += 1
                else:
                    failed += 1

            logger.info(f"Synced {synced} files to Convex")
            return {"synced": synced, "failed": failed}
        except Exception as e:
            logger.error(f"Error syncing files: {e}")
            return {"synced": 0, "failed": 0}

    # ============= مزامنة الإعدادات =============

    def sync_settings_to_convex(self) -> bool:
        """مزامنة الإعدادات إلى Convex"""
        if not self.enabled:
            return False

        try:
            resp = supabase.table("bot_settings").select("*").execute()
            settings = resp.data or []

            for setting in settings:
                self._make_convex_request("setSetting", {
                    "key": setting["setting_key"],
                    "value": setting["setting_value"],
                    "description": setting.get("description"),
                })

            return True
        except Exception as e:
            logger.error(f"Error syncing settings: {e}")
            return False

    # ============= مزامنة روابط الخدمات =============

    def sync_service_links_to_convex(self) -> Dict[str, int]:
        """مزامنة روابط الخدمات"""
        if not self.enabled:
            return {"synced": 0}

        try:
            resp = supabase.table("service_links").select("*").execute()
            links = resp.data or []

            synced = 0
            for link in links:
                result = self._make_convex_request("addServiceLink", {
                    "name": link["name"],
                    "url": link["url"],
                    "icon": link.get("icon", "🔗"),
                    "description": link.get("description"),
                    "sort_order": link.get("sort_order", 0),
                })
                if result:
                    synced += 1

            return {"synced": synced}
        except Exception as e:
            logger.error(f"Error syncing service links: {e}")
            return {"synced": 0}

    # ============= مزامنة كاملة =============

    def full_sync_to_convex(self) -> Dict[str, Any]:
        """مزامنة كاملة من Supabase إلى Convex"""
        if not self.enabled:
            return {"error": "Sync service not enabled"}

        results = {}
        
        logger.info("Starting full sync to Convex...")
        
        results["users"] = self.sync_all_users_to_convex()
        results["admins"] = self.sync_all_admins_to_convex()
        results["categories_subjects"] = self.sync_all_categories_and_subjects()
        results["files"] = self.sync_all_files_to_convex()
        results["settings"] = {"success": self.sync_settings_to_convex()}
        results["service_links"] = self.sync_service_links_to_convex()

        logger.info(f"Full sync completed: {results}")
        return results

    # ============= مزامنة في الوقت الحقيقي =============

    def on_user_created(self, user_id: int, username: str = None, first_name: str = ""):
        """يُستدعى عند إنشاء مستخدم جديد"""
        self.sync_user_to_convex(user_id, username, first_name)

    def on_file_uploaded(self, file_data: Dict):
        """يُستدعى عند رفع ملف جديد"""
        self.sync_file_to_convex(file_data)

    def on_subject_created(self, subject_data: Dict):
        """يُستدعى عند إنشاء مادة جديدة"""
        self.sync_subject_to_convex(subject_data)

    def on_category_created(self, category_data: Dict):
        """يُستدعى عند إنشاء تصنيف جديد"""
        self.sync_category_to_convex(category_data)


# إنشاء instance عام
sync_service = SyncService()
