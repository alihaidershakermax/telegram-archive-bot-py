import os
import logging
import time
import asyncio
import threading
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.helpers import escape_markdown
from telegram.error import Conflict, BadRequest, Forbidden, TimedOut
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from supabase_client import supabase
from supabase_client import (
    can_user_ask_question,
    get_remaining_questions,
    create_ask_me_question,
    get_user_pending_questions,
    get_all_pending_questions,
    answer_question,
    close_question,
    get_question_by_id,
    subscribe_to_subject,
    unsubscribe_from_subject,
    is_subscribed_to_subject,
    get_subscribers_for_subject,
    get_user_subscriptions,
    mark_file_as_viewed,
    is_file_viewed,
    get_unread_files_for_user,
    add_to_favorites,
    remove_from_favorites,
    get_user_favorites,
    is_favorite,
    rate_file,
    get_file_rating,
    get_user_file_rating,
    rate_subject,
    get_subject_rating,
    get_subject_stats,
    get_user_file_stats,
    is_user_banned,
    ban_user,
    unban_user,
    get_user_question_limit,
    create_file_request,
    get_user_file_requests,
    get_all_pending_file_requests,
    fulfill_file_request,
    reject_file_request,
    get_file_request_by_id,
)
from sync_service import sync_service
from ai_service import (
    ask_ai,
    ask_ai_with_context,
    get_topic_keyboard,
    get_topic_questions,
    PETROLEUM_TOPICS,
    get_ai_client,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_env(key, default=None, required=True):
    val = os.environ.get(key, default)
    if required and not val:
        print(f"CRITICAL ERROR: Environment variable {key} is missing!")
        sys.exit(1)
    return val


BOT_TOKEN = get_env("BOT_TOKEN")
OWNER_ID = int(get_env("OWNER_ID"))
ARCHIVE_CHANNEL_ID = int(get_env("ARCHIVE_CHANNEL_ID"))

DEVELOPER = "@dextermorgenk"
BOT_USER = "@arcivealibot"
WELCOME_PHOTO = os.environ.get("WELCOME_PHOTO")  # Optional

WELCOME_MESSAGE = (
    "🎓 **منصة الأرشيف التعليمي الذكي**\n\n"
    "مرحباً بك! 👋\n\n"
    "الأرشيف التعليمي هو رفيقك الرقمي على تليجرام، المصمم خصيصاً لتبسيط الوصول إلى المصادر العلمية والملفات الأكاديمية بكل كفاءة وسرعة.\n\n"
    "💡 **ما نقدمه:**\n"
    "📂 تنظيم ذكي للملفات\n"
    "🔍 وصول سريع للمحتوى\n"
    "⭐ ملفاتك المفضلة\n\n"
)

ABOUT_DEV_TEXT = (
    "السلام عليكم ورحمة الله وبركاته\n\n"
    "هذا القسم مخصص للتعريف بالجهد المبذول خلف الكواليس، وضمان حفظ حقوق البرمجة والتطوير التي تهدف لخدمتكم.\n\n"
    "تم ابتكار هذا البوت ليكون جسراً يسهل عليكم الوصول إلى الملفات والمواد التعليمية، مع التركيز على تنظيمها بأسلوب ذكي وسلس يختصر عليكم الوقت والجهد.\n\n"
    "نحن نسعى دوماً للكمال، ولكن الخطأ وارد. إذا واجهت أي خلل تقني، أو كان لديك اقتراح لتطوير التجربة، يسعدنا تواصلك المباشر مع المطور:\n\n"
    f"👨‍💻 المطور: {DEVELOPER}\n\n"
    "شكراً لثقتكم بنا، ونتمنى أن يمثل هذا العمل إضافة حقيقية لرحلتكم التعليمية."
)

COMMANDS_TEXT = (
    "📌 *الأوامر المتاحة*\n\n"
    "/start — بدء البوت\n"
    "/panel — لوحة الإدارة (للأدمن)\n"
    "/about — حول المطور\n"
    "/search — البحث عن ملفات\n"
    "/ask — طرح سؤال للإدارة\n"
    "/ai — مهندس الذكاء الاصطناعي\n"
    "/mysubs — اشتراكاتي في المواد\n"
    "/unread — الملفات غير المقروءة\n"
    "/favorites — الملفات المفضلة\n"
    "/mystats — إحصائياتي الشخصية\n"
    "/stats — عرض الإحصائيات\n"
    "/help — عرض المساعدة\n"
    "/archive — عرض الأرشيف\n"
)


CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "60"))
USE_WEBHOOK = os.environ.get("USE_WEBHOOK", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
RUN_LOCAL_WEB_SERVER = os.environ.get(
    "RUN_LOCAL_WEB_SERVER", "true"
).strip().lower() in ("1", "true", "yes", "on")
MAX_USERS_SHOW = int(os.environ.get("MAX_USERS_SHOW", "200"))
USERS_PAGE_SIZE = int(os.environ.get("USERS_PAGE_SIZE", "25"))
ACTIVITY_PAGE_SIZE = int(os.environ.get("ACTIVITY_PAGE_SIZE", "25"))
BROADCAST_BATCH_SIZE = int(os.environ.get("BROADCAST_BATCH_SIZE", "25"))
BROADCAST_SLEEP_SECONDS = float(os.environ.get("BROADCAST_SLEEP_SECONDS", "0.2"))
BROADCAST_POLL_INTERVAL = float(os.environ.get("BROADCAST_POLL_INTERVAL", "5"))

# Fixed archive categories (ordered)
FIXED_CATEGORY_NAMES = [
    "محاضرات PDF",
    "ملخصات PDF",
    "محاضرات فيديوية",
    "محاضرات مترجمة",
]

_subjects_cache = {}
_files_cache = {}
_admins_cache = {"data": None, "ts": 0.0}
_users_cache = {"data": None, "ts": 0.0}
_subjects_count_cache = {"data": None, "ts": 0.0}
_categories_cache = {"data": None, "ts": 0.0}
_broadcast_worker_started = False

_maintenance_cache = {"enabled": None, "ts": 0.0}


def _is_maintenance_enabled():
    if _maintenance_cache["enabled"] is not None and _cache_valid(
        _maintenance_cache["ts"]
    ):
        return _maintenance_cache["enabled"]
    try:
        resp = (
            supabase.table("bot_settings")
            .select("setting_value")
            .eq("setting_key", "maintenance_mode")
            .limit(1)
            .execute()
        )
        row = _first_row(resp)
        val = (
            row["setting_value"].lower() == "true"
            if row and row.get("setting_value")
            else False
        )
        _maintenance_cache["enabled"] = val
        _maintenance_cache["ts"] = time.time()
        return val
    except:
        return False


def _set_maintenance_mode(enabled: bool):
    try:
        supabase.table("bot_settings").upsert(
            {"setting_key": "maintenance_mode", "setting_value": str(enabled).lower()},
            on_conflict="setting_key",
        ).execute()
        _maintenance_cache["enabled"] = enabled
        _maintenance_cache["ts"] = time.time()
    except Exception as e:
        logger.error(f"Failed to save maintenance mode: {e}")


PERMISSIONS = {
    "manage_subjects": "إدارة المواد",
    "delete_files": "حذف الملفات",
    "upload_files": "رفع الملفات",
    "broadcast": "إرسال إذاعة",
    "manage_admins": "إدارة الأدمنز",
    "view_users": "عرض المستخدمين",
    "view_activity": "عرض نشاط المستخدمين",
}


def get_main_keyboard(user_id=None):
    keyboard = [
        [KeyboardButton("📁 الملفات"), KeyboardButton("🔍 بحث")],
        [KeyboardButton("📢 اشتراكاتي"), KeyboardButton("⭐ المفضلة")],
        [KeyboardButton("🆕 غير مقروءة"), KeyboardButton("📊 إحصائياتي")],
        [KeyboardButton("🤖 مهندس الذكاء"), KeyboardButton("❓ سؤال للإدارة")],
        [KeyboardButton("🔗 خدماتنا"), KeyboardButton("🔙 الرئيسية")],
    ]
    if user_id and is_admin(user_id):
        keyboard.append([KeyboardButton("🛠 لوحة الأدمن")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_main_keyboard_admin():
    keyboard = [
        [KeyboardButton("📁 الملفات"), KeyboardButton("🔍 بحث")],
        [KeyboardButton("📢 اشتراكاتي"), KeyboardButton("⭐ المفضلة")],
        [KeyboardButton("🆕 غير مقروءة"), KeyboardButton("📊 إحصائياتي")],
        [KeyboardButton("🤖 مهندس الذكاء"), KeyboardButton("❓ سؤال للإدارة")],
        [KeyboardButton("🔗 خدماتنا"), KeyboardButton("🛠 لوحة الأدمن")],
        [KeyboardButton("🔙 الرئيسية")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def _cache_valid(ts):
    return (time.time() - ts) < CACHE_TTL_SECONDS


def _invalidate_subjects_cache():
    _subjects_cache.clear()


def _invalidate_categories_cache():
    _categories_cache["data"] = None
    _categories_cache["ts"] = 0.0


def _maintenance_enabled():
    return _is_maintenance_enabled()


def _invalidate_files_cache(subject_id=None):
    if subject_id is None:
        _files_cache.clear()
    else:
        _files_cache.pop(subject_id, None)


def _invalidate_admins_cache():
    _admins_cache["data"] = None
    _admins_cache["ts"] = 0.0


def _invalidate_users_cache():
    _users_cache["data"] = None
    _users_cache["ts"] = 0.0


def _invalidate_subjects_count_cache():
    _subjects_count_cache["data"] = None
    _subjects_count_cache["ts"] = 0.0


# ─── Database ─────────────────────────────────────────────────────────────────


def _first_row(resp):
    data = resp.data or []
    return data[0] if data else None


def _format_supabase_error(exc):
    parts = []
    for attr in ("message", "details", "hint", "code"):
        val = getattr(exc, attr, None)
        if val:
            parts.append(f"{attr}={val}")
    return "; ".join(parts) if parts else repr(exc)


def _ensure_fixed_categories():
    if not FIXED_CATEGORY_NAMES:
        return []
    for idx, name in enumerate(FIXED_CATEGORY_NAMES, start=1):
        try:
            supabase.table("categories").upsert(
                {"name": name, "sort_order": idx}, on_conflict="name"
            ).execute()
        except Exception:
            supabase.table("categories").upsert(
                {"name": name}, on_conflict="name"
            ).execute()
    resp = (
        supabase.table("categories")
        .select("*")
        .in_("name", FIXED_CATEGORY_NAMES)
        .execute()
    )
    rows = resp.data or []
    by_name = {r["name"]: r for r in rows}
    ordered = [by_name[name] for name in FIXED_CATEGORY_NAMES if name in by_name]
    return ordered


def _get_all_categories():
    """Get all categories including dynamically created ones."""
    resp = supabase.table("categories").select("*").order("sort_order").execute()
    rows = resp.data or []

    # Sort: fixed categories first by their order, then dynamic ones
    fixed_ids = set()
    for idx, name in enumerate(FIXED_CATEGORY_NAMES, start=1):
        for r in rows:
            if r.get("name") == name:
                r["_sort_priority"] = idx
                fixed_ids.add(r.get("id"))
                break

    # Mark dynamic categories
    for r in rows:
        if r.get("id") not in fixed_ids:
            r["_sort_priority"] = 999  # Put dynamic categories at the end

    # Sort by priority
    rows.sort(key=lambda x: x.get("_sort_priority", 999))
    return rows


def get_categories():
    if _categories_cache["data"] is not None and _cache_valid(_categories_cache["ts"]):
        return _categories_cache["data"]
    data = _get_all_categories()
    _categories_cache["data"] = data
    _categories_cache["ts"] = time.time()
    return data


def get_category_by_id(category_id):
    cats = get_categories()
    for c in cats:
        if c.get("id") == category_id:
            return c
    resp = (
        supabase.table("categories")
        .select("*")
        .eq("id", category_id)
        .limit(1)
        .execute()
    )
    return _first_row(resp)


def _subject_cache_key(category_id):
    return str(category_id) if category_id is not None else "all"


def get_subjects(category_id=None):
    key = _subject_cache_key(category_id)
    cached = _subjects_cache.get(key)
    if cached and _cache_valid(cached["ts"]):
        return cached["data"]
    try:
        query = supabase.table("subjects").select("*")
        if category_id is not None:
            query = query.eq("category_id", category_id)
        resp = query.order("name").execute()
        data = resp.data or []
        # Fallback: if old subjects have NULL category_id, show them under the first category
        if category_id is not None and not data:
            categories = get_categories()
            first_id = categories[0]["id"] if categories else None
            if first_id and category_id == first_id:
                all_resp = (
                    supabase.table("subjects").select("*").order("name").execute()
                )
                all_rows = all_resp.data or []
                data = [r for r in all_rows if r.get("category_id") in (None, first_id)]
    except Exception as exc:
        if category_id is not None and "category_id" in str(exc):
            cats = get_categories()
            first_id = cats[0]["id"] if cats else None
            if category_id == first_id:
                resp = supabase.table("subjects").select("*").order("name").execute()
                data = resp.data or []
            else:
                data = []
        else:
            raise
    _subjects_cache[key] = {"data": data, "ts": time.time()}
    return data


def get_files_for_subject(subject_id):
    cached = _files_cache.get(subject_id)
    if cached and _cache_valid(cached["ts"]):
        return cached["data"]
    resp = (
        supabase.table("files")
        .select("*")
        .eq("subject_id", subject_id)
        .order("name")
        .execute()
    )
    data = resp.data or []
    _files_cache[subject_id] = {"data": data, "ts": time.time()}
    return data


def get_subjects_with_file_counts():
    if _subjects_count_cache["data"] is not None and _cache_valid(
        _subjects_count_cache["ts"]
    ):
        return _subjects_count_cache["data"]
    try:
        resp = (
            supabase.table("subjects")
            .select("id,name,category_id,files(count)")
            .execute()
        )
        rows = resp.data or []
    except Exception as exc:
        if "category_id" in str(exc):
            resp = supabase.table("subjects").select("id,name,files(count)").execute()
            rows = resp.data or []
        else:
            raise

    categories = get_categories()
    if categories and rows and "category_id" in rows[0]:
        by_cat = {}
        for r in rows:
            by_cat.setdefault(r.get("category_id"), []).append(r)
        ordered = []
        for c in categories:
            for r in sorted(by_cat.get(c["id"], []), key=lambda x: x.get("name") or ""):
                ordered.append(r)
    else:
        ordered = sorted(rows, key=lambda x: x.get("name") or "")

    _subjects_count_cache["data"] = ordered
    _subjects_count_cache["ts"] = time.time()
    return ordered


def get_subject_by_id(subject_id):
    resp = (
        supabase.table("subjects").select("*").eq("id", subject_id).limit(1).execute()
    )
    return _first_row(resp)


def create_subject(name, category_id=None):
    payload = {"name": name}
    if category_id is not None:
        payload["category_id"] = category_id
    try:
        supabase.table("subjects").upsert(payload, on_conflict="name").execute()
    except Exception as exc:
        if "category_id" in str(exc):
            payload.pop("category_id", None)
            supabase.table("subjects").upsert(payload, on_conflict="name").execute()
        else:
            raise
    resp = supabase.table("subjects").select("id").eq("name", name).limit(1).execute()
    row = _first_row(resp)
    _invalidate_subjects_cache()
    _invalidate_subjects_count_cache()
    # Sync to Convex
    if row:
        sync_service.on_subject_created(
            {"id": row["id"], "name": name, "category_id": category_id}
        )
    return row["id"] if row else None


async def notify_subscribers_of_new_file(
    application, subject_id, file_name, file_id, file_type
):
    """Notify all subscribers of a subject when a new file is added."""
    try:
        subscribers = get_subscribers_for_subject(subject_id)
        subject = get_subject_by_id(subject_id)
        if not subject:
            return

        subject_name = subject["name"]

        # Determine emoji based on file type
        type_emoji = {
            "document": "📄",
            "video": "🎥",
            "audio": "🎵",
            "photo": "📷",
            "voice": "🎤",
        }.get(file_type, "📄")

        for sub in subscribers:
            try:
                await application.bot.send_message(
                    chat_id=sub["user_id"],
                    text=(
                        f"📢 *ملف جديد في المادة!*\n\n"
                        f"📚 المادة: *{subject_name}*\n"
                        f"{type_emoji} الملف: *{file_name}*\n\n"
                        "افتح البوت للوصول إلى الملف."
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning(f"Failed to notify subscriber {sub['user_id']}: {e}")
    except Exception as e:
        logger.error(f"Error notifying subscribers: {e}")


def save_file(name, file_id, file_type, subject_id, message_id, file_size=None):
    try:
        file_record = {
            "name": name,
            "file_id": file_id,
            "file_type": file_type,
            "subject_id": subject_id,
            "message_id": message_id,
        }
        if file_size is not None:
            file_record["file_size"] = file_size

        supabase.table("files").insert(file_record).execute()
        _invalidate_files_cache(subject_id)
        _invalidate_subjects_count_cache()
        # Sync to Convex
        sync_service.on_file_uploaded(file_record)
    except Exception as e:
        logger.error(f"Error saving file {name} to database: {e}")
        raise


def delete_subject(subject_id):
    supabase.table("subjects").delete().eq("id", subject_id).execute()
    _invalidate_subjects_cache()
    _invalidate_files_cache(subject_id)
    _invalidate_subjects_count_cache()


def delete_file(file_db_id):
    resp = (
        supabase.table("files")
        .select("subject_id")
        .eq("id", file_db_id)
        .limit(1)
        .execute()
    )
    row = _first_row(resp)
    supabase.table("files").delete().eq("id", file_db_id).execute()
    if row and row.get("subject_id") is not None:
        _invalidate_files_cache(row["subject_id"])
        _invalidate_subjects_count_cache()


def get_file_row(file_db_id):
    resp = (
        supabase.table("files")
        .select("id,name,file_id,file_type,subject_id,message_id, subjects(name)")
        .eq("id", file_db_id)
        .limit(1)
        .execute()
    )
    row = _first_row(resp)
    if not row:
        return None
    subject = row.get("subjects") or {}
    row["subject_name"] = subject.get("name")
    return row


def save_user(user):
    payload = {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        supabase.table("users").upsert(payload).execute()
    except Exception as e:
        # Fallback if schema cache doesn't have last_seen_at yet
        msg = str(e)
        if "last_seen_at" in msg:
            payload.pop("last_seen_at", None)
            supabase.table("users").upsert(payload).execute()
        else:
            raise
    _invalidate_users_cache()
    # Sync to Convex
    sync_service.on_user_created(user.id, user.username, user.first_name)


def log_activity(user, action, details=None):
    # Skip logging simple navigation to save Supabase API requests
    ignored_actions = [
        "view_archive",
        "view_subject",
        "view_file",
        "back_main",
        "about",
        "about_bot",
        "commands",
        "start",
        "adm_back",
        "panel",
        "ask_me_menu",
        "search_menu",
    ]
    if action in ignored_actions:
        return

    try:
        supabase.table("user_activity").insert(
            {
                "user_id": user.id,
                "action": action,
                "details": details,
            }
        ).execute()
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


def _extract_broadcast_payload(message):
    if message.text:
        return {
            "kind": "text",
            "text": message.text,
            "parse_mode": "Markdown",
        }
    caption = message.caption or ""
    if message.document:
        return {
            "kind": "document",
            "file_id": message.document.file_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }
    if message.video:
        return {
            "kind": "video",
            "file_id": message.video.file_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }
    if message.audio:
        return {
            "kind": "audio",
            "file_id": message.audio.file_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }
    if message.photo:
        return {
            "kind": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }
    if message.voice:
        return {
            "kind": "voice",
            "file_id": message.voice.file_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }
    if message.animation:
        return {
            "kind": "animation",
            "file_id": message.animation.file_id,
            "caption": caption,
            "parse_mode": "Markdown",
        }
    if message.video_note:
        return {"kind": "video_note", "file_id": message.video_note.file_id}
    if message.sticker:
        return {"kind": "sticker", "file_id": message.sticker.file_id}
    return None


def enqueue_broadcast(payload, created_by):
    supabase.table("broadcasts").insert(
        {
            "created_by": created_by,
            "status": "pending",
            "payload": payload,
        }
    ).execute()


def _get_users_count():
    resp = supabase.table("users").select("id", count="exact").execute()
    if resp.count is not None:
        return int(resp.count)
    return len(resp.data or [])


def _get_users_batch(after_id, limit):
    resp = (
        supabase.table("users")
        .select("id")
        .gt("id", after_id)
        .order("id")
        .limit(limit)
        .execute()
    )
    rows = resp.data or []
    return [r["id"] for r in rows]


def _get_next_broadcast_job():
    resp = (
        supabase.table("broadcasts")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(1)
        .execute()
    )
    row = _first_row(resp)
    if row:
        return row
    resp = (
        supabase.table("broadcasts")
        .select("*")
        .eq("status", "sending")
        .order("created_at")
        .limit(1)
        .execute()
    )
    return _first_row(resp)


def _claim_broadcast_job(job_id):
    resp = (
        supabase.table("broadcasts")
        .update(
            {"status": "sending", "started_at": datetime.now(timezone.utc).isoformat()}
        )
        .eq("id", job_id)
        .eq("status", "pending")
        .execute()
    )
    return bool(resp.data)


def _update_broadcast_job(job_id, updates):
    supabase.table("broadcasts").update(updates).eq("id", job_id).execute()


async def _send_payload_with_fallback(bot, send_func, **kwargs):
    try:
        if hasattr(send_func, "__self__"):  # bound method like bot.send_message
            return await send_func(**kwargs)
        else:  # function like send_file_by_type
            return await send_func(bot, **kwargs)
    except BadRequest as exc:
        err = str(exc).lower()
        if "can't parse entities" in err or "can't parse" in err:
            kwargs.pop("parse_mode", None)
            if hasattr(send_func, "__self__"):
                return await send_func(**kwargs)
            else:
                return await send_func(bot, **kwargs)
        raise


async def _send_broadcast_payload(bot, user_id, payload):
    kind = payload.get("kind")
    if kind == "text":
        return await _send_payload_with_fallback(
            bot,
            bot.send_message,
            chat_id=user_id,
            text=payload.get("text", ""),
            parse_mode=payload.get("parse_mode"),
        )
    if kind in ("document", "video", "audio", "photo", "voice", "animation"):
        return await _send_payload_with_fallback(
            bot,
            send_file_by_type,
            chat_id=user_id,
            file_id=payload.get("file_id"),
            file_type=kind,
            caption=payload.get("caption") or None,
            parse_mode=payload.get("parse_mode"),
        )
    if kind == "video_note":
        return await send_file_by_type(
            bot, user_id, payload.get("file_id"), "video_note"
        )
    if kind == "sticker":
        return await send_file_by_type(bot, user_id, payload.get("file_id"), "sticker")
    return None


async def _process_broadcast_job(bot, job):
    job_id = job["id"]
    status = job.get("status")
    payload = job.get("payload") or {}
    if status == "pending":
        if not _claim_broadcast_job(job_id):
            return
        total_users = _get_users_count()
        _update_broadcast_job(job_id, {"total_users": total_users})
        job["total_users"] = total_users
        job["status"] = "sending"

    last_user_id = job.get("last_user_id") or 0
    sent = int(job.get("sent_count") or 0)
    failed = int(job.get("failed_count") or 0)

    users = _get_users_batch(last_user_id, BROADCAST_BATCH_SIZE)
    if not users:
        _update_broadcast_job(
            job_id,
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "sent_count": sent,
                "failed_count": failed,
            },
        )
        return

    for u_id in users:
        try:
            await _send_broadcast_payload(bot, u_id, payload)
            sent += 1
        except BadRequest as exc:
            err = str(exc).lower()
            if "chat not found" in err or "user is deactivated" in err:
                try:
                    remove_user(u_id)
                except Exception:
                    logger.exception(
                        "Failed to remove user %s after bad request: %s", u_id, exc
                    )
            failed += 1
            logger.warning("Broadcast send bad request for user %s: %s", u_id, exc)
        except Forbidden as exc:
            err = str(exc).lower()
            if "bot was blocked by the user" in err or "user is deactivated" in err:
                try:
                    remove_user(u_id)
                except Exception:
                    logger.exception(
                        "Failed to remove user %s after forbidden: %s", u_id, exc
                    )
            failed += 1
            logger.warning("Broadcast send forbidden for user %s: %s", u_id, exc)
        except Exception as exc:
            failed += 1
            logger.warning("Broadcast send failed for user %s: %s", u_id, exc)

        last_user_id = u_id
        await asyncio.sleep(BROADCAST_SLEEP_SECONDS)

    _update_broadcast_job(
        job_id,
        {
            "last_user_id": last_user_id,
            "sent_count": sent,
            "failed_count": failed,
        },
    )


async def broadcast_worker(application):
    await asyncio.sleep(2)
    while True:
        try:
            job = _get_next_broadcast_job()
            if not job:
                await asyncio.sleep(BROADCAST_POLL_INTERVAL)
                continue
            await _process_broadcast_job(application.bot, job)
        except Exception as exc:
            logger.exception("Broadcast worker error: %s", exc)
            await asyncio.sleep(BROADCAST_POLL_INTERVAL)


def ensure_broadcast_worker(loop, application):
    global _broadcast_worker_started
    if _broadcast_worker_started:
        return
    _broadcast_worker_started = True

    def _starter():
        while True:
            try:
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        broadcast_worker(application), loop
                    )
                    break
            except Exception:
                pass
            time.sleep(0.2)

    threading.Thread(target=_starter, daemon=True).start()


def remove_user(user_id: int):
    supabase.table("users").delete().eq("id", user_id).execute()
    _invalidate_users_cache()


_settings_cache = {}


def get_bot_setting(key, default=None):
    if key in _settings_cache:
        return _settings_cache[key]
    try:
        resp = (
            supabase.table("bot_settings")
            .select("setting_value")
            .eq("setting_key", key)
            .limit(1)
            .execute()
        )
        row = _first_row(resp)
        val = row["setting_value"] if row else default
        _settings_cache[key] = val
        return val
    except:
        return default


def get_broadcast_buttons():
    try:
        resp = (
            supabase.table("buttons")
            .select("*")
            .eq("is_active", True)
            .order("sort_order")
            .execute()
        )
        return resp.data or []
    except:
        return []


def get_service_links():
    try:
        resp = (
            supabase.table("service_links")
            .select("*")
            .eq("is_active", True)
            .order("sort_order")
            .execute()
        )
        return resp.data or []
    except:
        return []


async def forward_to_archive(context, source_chat_id, message_id, notify_target):
    try:
        caption_prefix = get_bot_setting(
            "archive_caption_prefix", "📂 ملف جديد من الأرشيف التعليمي"
        )
        dev_username = get_bot_setting("developer_username", DEVELOPER)
        bot_username = get_bot_setting("bot_username", BOT_USER)
        footer = f"\n\n👨‍💻 المطور: {dev_username}\n🤖 البوت: {bot_username}"

        return await context.bot.copy_message(
            chat_id=ARCHIVE_CHANNEL_ID,
            from_chat_id=source_chat_id,
            message_id=message_id,
            caption=f"{caption_prefix}{footer}",
            parse_mode="Markdown",
        )
    except BadRequest as exc:
        msg = str(exc)
        if "chat not found" in msg.lower():
            await notify_target.reply_text(
                "⚠️ تعذّر الإرسال للأرشيف.\n"
                "تأكد أن البوت مضاف كأدمن في قناة الأرشيف وأن ARCHIVE_CHANNEL_ID صحيح (عادة يبدأ بـ -100)."
            )
            return None
        elif "message to forward not found" in msg.lower():
            await notify_target.reply_text(
                "⚠️ تعذّر إيجاد الرسالة المراد إرسالها للأرشيف."
            )
            return None
        elif "user is deactivated" in msg.lower() or "chat not found" in msg.lower():
            logger.warning(f"Forward failed due to deactivated user or chat: {exc}")
            return None
        logger.error(f"Forward failed with error: {exc}")
        raise
    except Exception as exc:
        logger.error(f"Unexpected error during forwarding: {exc}")
        await notify_target.reply_text("⚠️ حدث خطأ أثناء إرسال الملف للأرشيف.")
        return None


def get_all_users():
    if _users_cache["data"] is not None and _cache_valid(_users_cache["ts"]):
        return _users_cache["data"]
    resp = supabase.table("users").select("id").execute()
    data = [r["id"] for r in (resp.data or [])]
    _users_cache["data"] = data
    _users_cache["ts"] = time.time()
    return data


def get_all_users_details(limit=MAX_USERS_SHOW):
    resp = (
        supabase.table("users")
        .select("id,username,first_name")
        .order("id")
        .limit(limit)
        .execute()
    )
    return resp.data or []


def get_users_page(offset, limit):
    resp = (
        supabase.table("users")
        .select("id,username,first_name")
        .order("id")
        .range(offset, offset + limit - 1)
        .execute()
    )
    return resp.data or []


def build_users_page_text_and_keyboard(page):
    total_users = len(get_all_users())
    if total_users <= 0:
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
        return "👥 *قائمة المستخدمين*\n\nلا يوجد مستخدمون بعد.", InlineKeyboardMarkup(
            kb
        )

    per_page = max(1, USERS_PAGE_SIZE)
    max_page = max(1, (total_users + per_page - 1) // per_page)
    page = max(1, min(page, max_page))
    offset = (page - 1) * per_page

    users = get_users_page(offset, per_page)
    lines = [
        "👥 *قائمة المستخدمين*",
        f"الصفحة: *{page}/{max_page}*  |  العدد: *{total_users}*",
        "",
    ]

    for u in users:
        label = _format_user_label_md(u)
        lines.append(f"• {label} (ID:{u['id']})")

    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton("⬅️ السابق", callback_data=f"adm_users_{page - 1}")
        )
    if page < max_page:
        nav.append(
            InlineKeyboardButton("التالي ➡️", callback_data=f"adm_users_{page + 1}")
        )

    kb = []
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")])
    return "\n".join(lines), InlineKeyboardMarkup(kb)


def get_activity_count():
    resp = supabase.table("user_activity").select("id", count="exact").execute()
    if hasattr(resp, "count") and resp.count is not None:
        return resp.count
    return len(resp.data or [])


def get_activity_page(offset, limit):
    resp = (
        supabase.table("user_activity")
        .select("id,action,details,created_at, users(id,username,first_name)")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return resp.data or []


def build_activity_page_text_and_keyboard(page):
    total = get_activity_count()
    if total <= 0:
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
        return "📈 *نشاط المستخدمين*\n\nلا يوجد نشاط بعد.", InlineKeyboardMarkup(kb)

    per_page = max(1, ACTIVITY_PAGE_SIZE)
    max_page = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, max_page))
    offset = (page - 1) * per_page

    rows = get_activity_page(offset, per_page)
    lines = [
        "📈 *نشاط المستخدمين*",
        f"الصفحة: *{page}/{max_page}*  |  العدد: *{total}*",
        "",
    ]
    for r in rows:
        user = r.get("users") or {}
        label = _format_user_label_md(user) if user else "مستخدم"
        action = escape_markdown(r.get("action") or "", version=1)
        details = r.get("details") or ""
        details = escape_markdown(details, version=1)
        when = r.get("created_at") or ""
        when = escape_markdown(when, version=1)
        line = f"• {label} — *{action}*"
        if details:
            line += f" | {details}"
        if when:
            line += f" | {when}"
        lines.append(line)

    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton("⬅️ السابق", callback_data=f"adm_activity_{page - 1}")
        )
    if page < max_page:
        nav.append(
            InlineKeyboardButton("التالي ➡️", callback_data=f"adm_activity_{page + 1}")
        )
    kb = []
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")])
    return "\n".join(lines), InlineKeyboardMarkup(kb)


def get_admins():
    if _admins_cache["data"] is not None and _cache_valid(_admins_cache["ts"]):
        return _admins_cache["data"]
    resp = supabase.table("admins").select("*").order("added_at").execute()
    data = resp.data or []
    _admins_cache["data"] = data
    _admins_cache["ts"] = time.time()
    return data


def add_admin(user_id, username, first_name):
    try:
        resp = (
            supabase.table("admins")
            .upsert(
                {
                    "id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "manage_subjects": True,
                    "delete_files": True,
                    "upload_files": True,
                    "broadcast": True,
                    "manage_admins": True,
                    "view_users": True,
                    "view_activity": True,
                }
            )
            .execute()
        )
        if getattr(resp, "error", None):
            raise RuntimeError(str(resp.error))
        _invalidate_admins_cache()
    except Exception as exc:
        raise RuntimeError(_format_supabase_error(exc)) from exc


def remove_admin(user_id):
    supabase.table("admins").delete().eq("id", user_id).execute()
    _invalidate_admins_cache()


def is_admin_in_db(user_id):
    admins = get_admins()
    return any(admin.get("id") == user_id for admin in admins)


def is_owner(uid):
    return uid == OWNER_ID


def is_admin(uid):
    return uid == OWNER_ID or is_admin_in_db(uid)


def get_admin_by_id(user_id):
    for a in get_admins():
        if a.get("id") == user_id:
            return a
    return None


def admin_can(uid, perm):
    if is_owner(uid):
        return True
    admin = get_admin_by_id(uid)
    if not admin:
        return False
    val = admin.get(perm)
    if val is None:
        return True
    return bool(val)


def _perm_enabled(admin, perm):
    val = admin.get(perm)
    if val is None:
        return True
    return bool(val)


def _format_user_label_plain(user):
    name = (user.get("first_name") or "").strip()
    uname = f"@{user['username']}" if user.get("username") else ""
    return " ".join(p for p in [name, uname] if p) or f"ID:{user.get('id', '?')}"


def _format_user_label_md(user):
    return escape_markdown(_format_user_label_plain(user), version=1)


def get_file_from_message(message):
    if message.document:
        return (
            message.document.file_id,
            (message.document.file_name or "ملف"),
            "document",
        )
    if message.video:
        return message.video.file_id, (message.video.file_name or "فيديو"), "video"
    if message.audio:
        return message.audio.file_id, (message.audio.file_name or "ملف صوتي"), "audio"
    if message.photo:
        return message.photo[-1].file_id, "صورة", "photo"
    if message.voice:
        return message.voice.file_id, "رسالة صوتية", "voice"
    if message.animation:
        return message.animation.file_id, "GIF", "animation"
    if message.video_note:
        return message.video_note.file_id, "رسالة فيديو", "video_note"
    if message.sticker:
        return message.sticker.file_id, "ملصق", "sticker"
    return None, None, None


def _build_file_filter():
    file_filter = (
        filters.Document.ALL
        | filters.VIDEO
        | filters.AUDIO
        | filters.PHOTO
        | filters.VOICE
        | filters.ANIMATION
        | filters.VIDEO_NOTE
    )
    sticker_filter = getattr(filters, "Sticker", None)
    if sticker_filter is not None:
        file_filter = file_filter | getattr(sticker_filter, "ALL", sticker_filter)
    return file_filter


FILE_FILTER = _build_file_filter()


async def send_file_by_type(
    bot, chat_id, file_id, file_type, caption=None, parse_mode=None, reply_markup=None
):
    if file_type == "photo":
        return await bot.send_photo(
            chat_id=chat_id,
            photo=file_id,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    if file_type == "video":
        return await bot.send_video(
            chat_id=chat_id,
            video=file_id,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    if file_type == "audio":
        return await bot.send_audio(
            chat_id=chat_id,
            audio=file_id,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    if file_type == "voice":
        return await bot.send_voice(
            chat_id=chat_id,
            voice=file_id,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    if file_type == "animation":
        return await bot.send_animation(
            chat_id=chat_id,
            animation=file_id,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    if file_type == "video_note":
        return await bot.send_video_note(
            chat_id=chat_id, video_note=file_id, reply_markup=reply_markup
        )
    if file_type == "sticker":
        return await bot.send_sticker(
            chat_id=chat_id, sticker=file_id, reply_markup=reply_markup
        )
    return await bot.send_document(
        chat_id=chat_id,
        document=file_id,
        caption=caption,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


# ─── UI builders ──────────────────────────────────────────────────────────────


def build_archive_keyboard(user_id=None):
    categories = get_categories()
    keyboard = []
    if categories:
        for c in categories:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📚 {c['name']}", callback_data=f"cat_{c['id']}"
                    )
                ]
            )

    # Add create section button for admins
    if user_id and is_admin(user_id):
        keyboard.append(
            [InlineKeyboardButton("➕ إضافة قسم", callback_data="new_category")]
        )

    keyboard.append(
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_start")]
    )
    return InlineKeyboardMarkup(keyboard), categories


async def send_archive(target, edit=False, user_id=None):
    markup, categories = build_archive_keyboard(user_id)
    text = (
        "📁 *الملفات*\n\nاختر القسم لعرض المواد:"
        if categories
        else "📁 *الأرشيف فارغ حالياً.*\n\nأرسل ملفاً لإنشاء أول قسم."
    )

    # Handle different types of targets properly
    try:
        if edit:
            # Try to edit the message
            message = target.message if hasattr(target, "message") else target
            if message and (message.photo or message.video or message.document):
                await target.edit_message_caption(
                    caption=text, reply_markup=markup, parse_mode="Markdown"
                )
            else:
                await target.edit_message_text(
                    text, reply_markup=markup, parse_mode="Markdown"
                )
        else:
            # For non-edit mode, always send a new message
            # Check if target is a CallbackQuery (has answer method) or Update
            if hasattr(target, "answer") and callable(getattr(target, "answer")):
                # This is a CallbackQuery - use message.reply_text
                await target.message.reply_text(
                    text, reply_markup=markup, parse_mode="Markdown"
                )
            elif hasattr(target, "message") and hasattr(target.message, "chat"):
                # This is an Update object - use chat.send_message
                await target.message.chat.send_message(
                    text, reply_markup=markup, parse_mode="Markdown"
                )
            else:
                # Fallback - try to use reply_text
                await target.reply_text(
                    text, reply_markup=markup, parse_mode="Markdown"
                )
    except Exception as e:
        # If editing fails, fall back to sending a new message
        logger.warning(f"Failed to edit message: {e}")
        if hasattr(target, "message") and hasattr(target.message, "chat"):
            await target.message.chat.send_message(
                text, reply_markup=markup, parse_mode="Markdown"
            )
        else:
            await target.reply_text(text, reply_markup=markup, parse_mode="Markdown")


def build_subject_keyboard(subject_id, files, user_id):
    keyboard = []
    for f in files:
        if admin_can(user_id, "delete_files"):
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                    ),
                    InlineKeyboardButton(
                        "🗑", callback_data=f"del_file_{f['id']}_{subject_id}"
                    ),
                ]
            )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                    )
                ]
            )
    keyboard.append(
        [InlineKeyboardButton("🔙 رجوع للأرشيف", callback_data="back_main")]
    )
    if admin_can(user_id, "manage_subjects"):
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🗑 حذف المادة", callback_data=f"del_subject_{subject_id}"
                )
            ]
        )
    return InlineKeyboardMarkup(keyboard)


def build_category_subjects_keyboard(
    category_id, subjects, user_id, include_add_new=True, for_upload=False
):
    cb_prefix = "addto" if for_upload else "subject"
    keyboard = [
        [
            InlineKeyboardButton(
                f"📁 {s['name']}", callback_data=f"{cb_prefix}_{s['id']}"
            )
        ]
        for s in subjects
    ]
    if include_add_new and admin_can(user_id, "manage_subjects"):
        keyboard.append(
            [
                InlineKeyboardButton(
                    "➕ إنشاء مادة جديدة", callback_data=f"new_subject_{category_id}"
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("🔙 رجوع للأرشيف", callback_data="back_main")]
    )
    return InlineKeyboardMarkup(keyboard)


def build_panel_keyboard(user_id):
    rows = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="adm_stats")],
    ]
    if is_admin(user_id):
        toggle_label = (
            "🟢 إيقاف الصيانة" if _maintenance_enabled() else "🔧 تفعيل الصيانة"
        )
        rows.append(
            [InlineKeyboardButton(toggle_label, callback_data="adm_toggle_maintenance")]
        )
    if admin_can(user_id, "view_users"):
        rows.append(
            [InlineKeyboardButton("👥 عرض المستخدمين", callback_data="adm_users")]
        )
    if admin_can(user_id, "view_activity"):
        rows.append(
            [InlineKeyboardButton("📈 نشاط المستخدمين", callback_data="adm_activity")]
        )
    # Ask Me Questions
    if is_admin(user_id):
        pending_count = len(get_all_pending_questions())
        ask_label = (
            f"❓ أسئلة الطلاب ({pending_count})"
            if pending_count > 0
            else "❓ أسئلة الطلاب"
        )
        rows.append([InlineKeyboardButton(ask_label, callback_data="adm_ask_me")])

        # File Requests
        try:
            file_requests_count = len(get_all_pending_file_requests())
            req_label = (
                f"📄 طلبات الملفات ({file_requests_count})"
                if file_requests_count > 0
                else "📄 طلبات الملفات"
            )
            rows.append(
                [InlineKeyboardButton(req_label, callback_data="adm_file_requests")]
            )
        except Exception:
            pass  # Table might not exist yet
    # Fixed sections: no subject management UI
    if admin_can(user_id, "manage_admins"):
        rows.append(
            [InlineKeyboardButton("👥 إدارة الأدمنز", callback_data="adm_admins")]
        )
    if is_owner(user_id):
        rows.append(
            [InlineKeyboardButton("⚙️ صلاحيات الأدمنز", callback_data="adm_permissions")]
        )
    if admin_can(user_id, "broadcast"):
        rows.append(
            [InlineKeyboardButton("📢 إرسال إذاعة", callback_data="adm_broadcast")]
        )
    rows.append([InlineKeyboardButton("📁 الملفات", callback_data="adm_archive")])
    rows.append([InlineKeyboardButton("🔗 خدماتنا", callback_data="adm_services")])
    return InlineKeyboardMarkup(rows)


def get_admin_panel_keyboard(user_id):
    keyboard = []

    keyboard.append([KeyboardButton("📊 الإحصائيات")])

    if is_admin(user_id):
        toggle_label = (
            "🟢 إيقاف الصيانة" if _maintenance_enabled() else "🔧 تفعيل الصيانة"
        )
        keyboard.append([KeyboardButton(toggle_label)])

    if admin_can(user_id, "view_users"):
        keyboard.append([KeyboardButton("👥 عرض المستخدمين")])

    if admin_can(user_id, "view_activity"):
        keyboard.append([KeyboardButton("📈 نشاط المستخدمين")])

    if is_admin(user_id):
        pending_count = len(get_all_pending_questions())
        ask_label = (
            f"❓ أسئلة الطلاب ({pending_count})"
            if pending_count > 0
            else "❓ أسئلة الطلاب"
        )
        keyboard.append([KeyboardButton(ask_label)])

        # File requests
        try:
            file_requests_count = len(get_all_pending_file_requests())
            req_label = (
                f"📄 طلبات الملفات ({file_requests_count})"
                if file_requests_count > 0
                else "📄 طلبات الملفات"
            )
            keyboard.append([KeyboardButton(req_label)])
        except Exception:
            pass  # Table might not exist yet

    if admin_can(user_id, "manage_admins"):
        keyboard.append([KeyboardButton("👥 إدارة الأدمنز")])

    if is_owner(user_id):
        keyboard.append([KeyboardButton("⚙️ صلاحيات الأدمنز")])

    if admin_can(user_id, "broadcast"):
        keyboard.append([KeyboardButton("📢 إرسال إذاعة")])

    keyboard.append([KeyboardButton("📁 الملفات"), KeyboardButton("🔗 خدماتنا")])
    keyboard.append([KeyboardButton("🔙 الرئيسية")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def send_panel(target, user_id, edit=False):
    subjects = get_subjects_with_file_counts()
    total_files = 0
    for s in subjects:
        files = s.get("files") or []
        if (
            isinstance(files, list)
            and files
            and isinstance(files[0], dict)
            and "count" in files[0]
        ):
            total_files += files[0]["count"] or 0
    total_users = len(get_all_users())
    total_admins = len(get_admins())
    text = (
        "🛠 *لوحة إدارة البوت*\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📚 المواد: *{len(subjects)}*\n"
        f"📄 الملفات: *{total_files}*\n"
        f"👥 المستخدمون: *{total_users}*\n"
        f"🔑 الأدمنز: *{total_admins}*\n\n"
        "اختر أحد الخيارات:"
    )
    if edit:
        await target.edit_message_text(
            text, reply_markup=build_panel_keyboard(user_id), parse_mode="Markdown"
        )
    else:
        await target.reply_text(
            text, reply_markup=get_admin_panel_keyboard(user_id), parse_mode="Markdown"
        )


# ─── Handlers ─────────────────────────────────────────────────────────────────


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.message.from_user)
    log_activity(update.message.from_user, "start")

    uid = update.message.from_user.id
    if is_user_banned(uid):
        await update.message.reply_text(
            "⛔ عذراً، لقد تم حظرك من استخدام هذا البوت. تواصل مع الإدارة إذا كان هناك خطأ."
        )
        return

    if _maintenance_enabled() and not is_admin(uid):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Check if this is a group message
    if update.message.chat.type == "group" or update.message.chat.type == "supergroup":
        # For groups, show a simplified welcome
        await update.message.reply_text(
            "🎓 **منصة الأرشيف التعليمي**\n\n"
            "مرحباً بك في مجموعة الأرشيف! \n"
            "هذا البوت يساعدك على تنظيم المحتوى الدراسي.",
            parse_mode="Markdown",
        )
        return

    # Handle deep link: start=file_{id} from mobile app
    if context.args:
        param = context.args[0]
        if param.startswith("file_"):
            try:
                file_db_id = int(param.split("_")[1])
                row = get_file_row(file_db_id)
                if row:
                    mark_file_as_viewed(uid, file_db_id)
                    log_activity(
                        update.message.from_user, "download_file", row.get("name")
                    )
                    is_fav = is_favorite(uid, file_db_id)
                    rating_info = get_file_rating(file_db_id)

                    keyboard = []
                    fav_label = "⭐ إزالة من المفضلة" if is_fav else "⭐ إضافة للمفضلة"
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                fav_label, callback_data=f"toggle_fav_{file_db_id}"
                            )
                        ]
                    )
                    user_rating = get_user_file_rating(uid, file_db_id)
                    rating_kb = []
                    for stars in range(1, 6):
                        icon = (
                            "⭐"
                            if (user_rating and stars <= user_rating) or not user_rating
                            else "☆"
                        )
                        rating_kb.append(
                            InlineKeyboardButton(
                                icon, callback_data=f"rate_file_{file_db_id}_{stars}"
                            )
                        )
                    keyboard.append(rating_kb)
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                "📥 العودة للأرشيف", callback_data="show_archive"
                            )
                        ]
                    )

                    await send_file_by_type(
                        bot=context.bot,
                        chat_id=update.message.chat_id,
                        file_id=row["file_id"],
                        file_type=(row.get("file_type") or "document"),
                        caption=(
                            f"📁 *{row['subject_name']}*\n"
                            f"📄 {row['name']}\n"
                            f"⭐ التقييم: *{rating_info['avg']:.1f}* من 5 ({rating_info['count']} تقييم)\n\n"
                            f"👨‍💻 {DEVELOPER}"
                        ),
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown",
                    )
                    return
            except (ValueError, IndexError):
                pass

    # For private chats, show the welcome message with Reply Keyboard
    welcome_text = WELCOME_MESSAGE
    uid = update.message.from_user.id

    if WELCOME_PHOTO:
        await update.message.reply_photo(
            photo=WELCOME_PHOTO,
            caption=welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(uid),
        )
    else:
        await update.message.reply_text(
            welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard(uid)
        )


async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return
    await send_panel(update.message, update.message.from_user.id)


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user by ID."""
    uid = update.message.from_user.id
    if not is_admin(uid):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ يرجى إرسال الآيدي بعد الأمر. مثال:\n`/ban 12345678`",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
        if target_id == OWNER_ID or is_admin(target_id):
            await update.message.reply_text("⛔ لا يمكن حظر المالك أو المشرفين.")
            return

        ban_user(target_id)
        log_activity(update.message.from_user, "ban_user", str(target_id))
        await update.message.reply_text(
            f"✅ تم حظر المستخدم `{target_id}` بنجاح.", parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("⚠️ آيدي غير صالح.")
    except Exception as e:
        logger.error(f"Ban error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء الحظر.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user by ID."""
    uid = update.message.from_user.id
    if not is_admin(uid):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ يرجى إرسال الآيدي بعد الأمر. مثال:\n`/unban 12345678`",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
        unban_user(target_id)
        log_activity(update.message.from_user, "unban_user", str(target_id))
        await update.message.reply_text(
            f"✅ تم إلغاء حظر المستخدم `{target_id}` بنجاح.", parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("⚠️ آيدي غير صالح.")
    except Exception as e:
        logger.error(f"Unban error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء إلغاء الحظر.")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_activity(update.message.from_user, "about")
    if _maintenance_enabled() and not is_admin(update.message.from_user.id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return
    await update.message.reply_text(ABOUT_DEV_TEXT, parse_mode="Markdown")


async def commands_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_activity(update.message.from_user, "commands")
    if _maintenance_enabled() and not is_admin(update.message.from_user.id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return
    await update.message.reply_text(COMMANDS_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display help text for the bot"""
    log_activity(update.message.from_user, "help")

    if _maintenance_enabled() and not is_admin(update.message.from_user.id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Check if this is a group message
    if update.message.chat.type == "group" or update.message.chat.type == "supergroup":
        # For groups, show group-specific help
        help_text = (
            "🎓 **مساعدة المجموعة**\n\n"
            "هذا البوت مصمم لتنظيم المحتوى الدراسي في المجموعات:\n\n"
            "📋 *الأوامر الأساسية:*\n"
            "/archive - عرض الأرشيف الكامل\n"
            "/stats - عرض إحصائيات المجموعة\n"
            "/search [اسم الملف] - البحث في الأرشيف\n\n"
            "📌 *ملاحظات:*\n"
            "• يُفضل إضافة البوت كمسؤول في المجموعة\n"
            "• يمكن للمستخدمين الوصول إلى الملفات عبر الأوامر\n"
            "• جميع الملفات تُحفظ في قنوات الأرشيف"
        )
    else:
        # For private chats, show regular help
        help_text = (
            "🎓 **مساعدة البوت**\n\n"
            "هذا البوت يساعدك على تنظيم المحتوى الدراسي:\n\n"
            "📋 *الأوامر الأساسية:*\n"
            "/start - بدء استخدام البوت\n"
            "/archive - عرض الأرشيف الكامل\n"
            "/stats - عرض الإحصائيات الشخصية\n"
            "/search [اسم الملف] - البحث في الأرشيف\n"
            "/mysubs - اشتراكاتي في المواد\n"
            "/unread - الملفات غير المقروءة\n"
            "/favorites - الملفات المفضلة\n"
            "/mystats - إحصائياتي الشخصية\n"
            "/ask - طرح سؤال للإدارة\n"
            "/panel - لوحة الإدارة (للأدمن)\n\n"
            "📌 *ملاحظات:*\n"
            '• استخدم الزر "Browse Archive" لتصفح الأرشيف\n'
            "• يمكنك الاشتراك في المواد لتستلم الإشعارات\n"
            "• يمكنك إضافة الملفات للمفضلة للوصول السريع"
        )

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display statistics for the bot"""
    log_activity(update.message.from_user, "stats")

    if _maintenance_enabled() and not is_admin(update.message.from_user.id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Check if this is a group message
    if update.message.chat.type == "group" or update.message.chat.type == "supergroup":
        # For groups, show group-specific stats
        await update.message.reply_text(
            "📊 *إحصائيات المجموعة*\n\n"
            "هذه الميزات متوفرة في المجموعات:\n"
            "• عدد المستخدمين في المجموعة\n"
            "• عدد الملفات المُرفقة\n"
            "• إحصائيات الاستخدام\n\n"
            "استخدم /archive لعرض الأرشيف الكامل.",
            parse_mode="Markdown",
        )
        return

    # For private chats, show user stats
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    # Get user stats
    stats = get_user_file_stats(user_id)
    viewed_count = stats["viewed_count"]

    # Get subscriptions count
    subscriptions = get_user_subscriptions(user_id)
    subs_count = len(subscriptions)

    # Get favorites count
    favorites = get_user_favorites(user_id)
    favs_count = len(favorites)

    # Get questions asked
    limit_info = get_user_question_limit(user_id)
    questions_asked = limit_info["questions_asked"]

    lines = [
        "📊 *إحصائياتي الشخصية*\n",
        f"📄 الملفات المقروءة: *{viewed_count}*",
        f"📚 المواد المشتركة: *{subs_count}*",
        f"⭐ الملفات المفضلة: *{favs_count}*",
        f"❓ الأسئلة المرسلة: *{questions_asked}* من 3",
    ]

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _maintenance_enabled() and not is_admin(update.message.from_user.id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "🔍 *استخدم الأمر هكذا:*\n`/search اسم_الملف`", parse_mode="Markdown"
        )
        return

    search_term = " ".join(context.args)
    log_activity(update.message.from_user, "search", search_term)

    # Search for files by name
    try:
        resp = (
            supabase.table("files")
            .select("*, subjects(name)")
            .ilike("name", f"%{search_term}%")
            .order("name")
            .limit(20)  # Limit results to prevent spam
            .execute()
        )

        files = resp.data or []

        if not files:
            safe_term = search_term.replace("*", "").replace("_", "")
            await update.message.reply_text(
                f"❌ لم يتم العثور على ملفات تحتوي على: {safe_term}",
            )
            return

        # Group files by subject
        files_by_subject = {}
        for file in files:
            subject = file.get("subjects", {})
            subject_name = subject.get("name", "غير مصنف")

            if subject_name not in files_by_subject:
                files_by_subject[subject_name] = []
            files_by_subject[subject_name].append(file)

        # Build response message
        safe_search = search_term.replace("*", "").replace("_", "")
        response_parts = [f"🔍 نتائج البحث عن: {safe_search}\n"]

        for subject_name, subject_files in files_by_subject.items():
            safe_subject = subject_name.replace("*", "").replace("_", "")
            response_parts.append(f"\n📚 {safe_subject}:")
            for file in subject_files:
                safe_name = (file.get("name") or "").replace("*", "").replace("_", "")
                response_parts.append(f"  • 📄 {safe_name}")

        response_parts.append(f"\n🔢 إجمالي النتائج: {len(files)}")

        # Create inline keyboard with first few results
        keyboard = []
        for i, file in enumerate(files[:5]):  # Show first 5 results as buttons
            file_name = (
                (file.get("name") or "ملف").replace("*", "").replace("_", "")[:30]
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📄 {file_name}{'...' if len(file.get('name', '')) > 30 else ''}",
                        callback_data=f"file_{file['id']}",
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

        await update.message.reply_text(
            "\n".join(response_parts),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء البحث. يرجى المحاولة لاحقاً.")


async def archive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the archive directly"""
    log_activity(update.message.from_user, "archive")

    if _maintenance_enabled() and not is_admin(update.message.from_user.id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Try to edit the previous message if it exists
    try:
        await update.message.delete()
    except:
        pass

    # Get categories and build keyboard
    user_id = update.message.from_user.id
    markup, categories = build_archive_keyboard(user_id)

    # Send archive message with inline keyboard showing categories
    await update.message.chat.send_message(
        "📁 *الملفات*\n\nاختر القسم لعرض المواد:"
        if categories
        else "📁 *الأرشيف فارغ حالياً.*\n\nأرسل ملفاً لإنشاء أول قسم.",
        parse_mode="Markdown",
        reply_markup=markup,
    )

    # Also send Reply Keyboard for main menu
    await update.message.chat.send_message(
        "📋 اختر من القائمة:",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id),
    )


async def ai_engineer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle AI Engineer button - Petroleum Engineering AI assistant."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    from ai_service import get_ai_client, get_topic_keyboard

    client = get_ai_client()
    if not client:
        await update.message.reply_text(
            "⚠️ *خدمة الذكاء الاصطناعي غير متاحة*\n\n"
            "لم يتم تكوين مفتاح API. يرجى التواصل مع الإدارة.",
            parse_mode="Markdown",
        )
        return

    keyboard = get_topic_keyboard()
    await update.message.reply_text(
        "🤖 *مهندس الذكاء الاصطناعي*\n\n"
        "مرحباً بك في مساعد الذكاء الاصطناعي المتخصص في هندسة النفط والغاز.\n\n"
        "اختر موضوع أو اكتب سؤالك مباشرة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ask command - Ask Me feature."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Check if user has questions remaining
    if not can_user_ask_question(user_id):
        await update.message.reply_text(
            "❌ *لقد استهلكت الحد المسموح من الأسئلة.*\n\n"
            "لديك حد أقصى 3 أسئلة فقط. إذا كان لديك سؤال عاجل، يرجى التواصل مع الإدارة.",
            parse_mode="Markdown",
        )
        return

    # Check if user has pending questions
    pending = get_user_pending_questions(user_id)
    if pending:
        await update.message.reply_text(
            "⏳ *لديك سؤال قيد الانتظار.*\n\n"
            "يرجى انتظار إجابة الإدارة على سؤالك قبل طرح سؤال جديد."
        )
        return

    # Set state for awaiting question
    context.user_data["awaiting_ask_question"] = True
    await update.message.reply_text(
        "❓ *اطرح سؤالك للإدارة*\n\n"
        "أرسل سؤالك الآن وسيقوم فريق الإدارة بالرد عليك.\n"
        f"⚠️ لديك {get_remaining_questions(user_id)} أسئلة متبقية.",
        parse_mode="Markdown",
    )


async def request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /request command - Request a file from admins."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Check if user provided a request text
    if context.args:
        request_text = " ".join(context.args)
    else:
        await update.message.reply_text(
            "📄 *طلب ملف جديد*\n\n"
            "استخدم الأمر هكذا:\n"
            "`/request اسم الملف الذي تريده`\n\n"
            "مثال:\n"
            "`/request محاضرات مادة الرياضيات الفصل الأول`",
            parse_mode="Markdown",
        )
        return

    # Create the file request
    request = create_file_request(user_id, request_text)
    if request:
        # Notify admins about the new request
        admins = get_admins()
        for admin in admins:
            try:
                await context.bot.send_message(
                    chat_id=admin["id"],
                    text=f"📄 *طلب ملف جديد*\n\n"
                    f"👤 المستخدم: @{update.message.from_user.username or update.message.from_user.first_name}\n"
                    f"🆔 ID: {user_id}\n\n"
                    f"📝 الطلب: {request_text}\n\n"
                    f"/request_{request['id']}",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin['id']}: {e}")

        await update.message.reply_text(
            "✅ *تم إرسال طلبك بنجاح!*\n\n"
            f"📝 الطلب: {request_text}\n\n"
            "📌 سيقوم فريق الإدارة بمراجعة طلبك وإضافته في حال توفره.\n\n"
            "💡 يمكنك متابعة طلباتك باستخدام /myrequests",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "❌ حدث خطأ أثناء إرسال الطلب. يرجى المحاولة لاحقاً."
        )


async def myrequests_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myrequests command - View user's file requests."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    requests = get_user_file_requests(user_id)

    if not requests:
        await update.message.reply_text(
            "📄 *طلباتك*\n\nلا توجد طلبات سابقة.\nاستخدم /request لطلب ملف.",
            parse_mode="Markdown",
        )
        return

    lines = ["📄 *طلباتك:*\n"]
    for req in requests:
        status_icon = (
            "✅"
            if req["status"] == "fulfilled"
            else "❌"
            if req["status"] == "rejected"
            else "⏳"
        )
        status_text = (
            "مكتمل"
            if req["status"] == "fulfilled"
            else "مرفوض"
            if req["status"] == "rejected"
            else "قيد الانتظار"
        )
        lines.append(f"{status_icon} {req['request_text']}")
        lines.append(f"   📌 الحالة: {status_text}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def fulfill_request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fulfill command - Mark a file request as fulfilled."""
    user_id = update.message.from_user.id

    if not admin_can(user_id, "upload_files"):
        await update.message.reply_text("⛔ غير مصرح.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ استخدم الأمر هكذا:\n`/fulfill_رقم_الطلب`\n\nمثال: `/fulfill_5`",
            parse_mode="Markdown",
        )
        return

    try:
        request_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ رقم الطلب غير صحيح.")
        return

    request = get_file_request_by_id(request_id)
    if not request:
        await update.message.reply_text("⚠️ الطلب غير موجود.")
        return

    if request["status"] != "pending":
        await update.message.reply_text(
            f"⚠️ هذا الطلب уже تم معالجته. الحالة: {request['status']}"
        )
        return

    fulfill_file_request(request_id, user_id)

    # Notify the user
    try:
        await context.bot.send_message(
            chat_id=request["user_id"],
            text="✅ *تم تنفيذ طلبك!*\n\n"
            f"📝 الطلب: {request['request_text']}\n\n"
            "📁 تم إضافة الملف الذي طلبته. تحقق من الأرشيف.",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to notify user: {e}")

    await update.message.reply_text(
        f"✅ تم تحديد الطلب #{request_id} كمكتمل!\n\n📝 {request['request_text']}",
        parse_mode="Markdown",
    )


async def reject_request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reject command - Reject a file request."""
    user_id = update.message.from_user.id

    if not admin_can(user_id, "upload_files"):
        await update.message.reply_text("⛔ غير مصرح.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ استخدم الأمر هكذا:\n`/reject_رقم_الطلب <السبب>`\n\n"
            "مثال: `/reject_5 الملف غير متوفر`",
            parse_mode="Markdown",
        )
        return

    try:
        request_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else None
    except ValueError:
        await update.message.reply_text("⚠️ رقم الطلب غير صحيح.")
        return

    request = get_file_request_by_id(request_id)
    if not request:
        await update.message.reply_text("⚠️ الطلب غير موجود.")
        return

    if request["status"] != "pending":
        await update.message.reply_text(
            f"⚠️ هذا الطلب bereits تم معالجته. الحالة: {request['status']}"
        )
        return

    reject_file_request(request_id, user_id, reason)

    # Notify the user
    try:
        reason_text = f"\n📝 السبب: {reason}" if reason else ""
        await context.bot.send_message(
            chat_id=request["user_id"],
            text="❌ *تم رفض طلبك*\n\n"
            f"📝 الطلب: {request['request_text']}\n"
            f"{reason_text}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Failed to notify user: {e}")

    reason_msg = f"\n📝 السبب: {reason}" if reason else ""
    await update.message.reply_text(
        f"❌ تم رفض الطلب #{request_id}!{reason_msg}",
        parse_mode="Markdown",
    )


async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /echo command - Enable/disable echo mode."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Toggle echo mode
    if context.user_data.get("echo_mode_enabled", False):
        context.user_data["echo_mode_enabled"] = False
        await update.message.reply_text(
            "✅ *وضع الإيكو معطل*\n\nالآن سيتم التعامل مع الرسائل بشكل طبيعي.",
            parse_mode="Markdown",
        )
    else:
        context.user_data["echo_mode_enabled"] = True
        await update.message.reply_text(
            "🔁 *وضع الإيكو مُفعّل*\n\n"
            "كل ما ترسله الآن سيتم إعادة إرساله لك.\n"
            "لإيقاف الوضع، أرسل /echo مرة أخرى.",
            parse_mode="Markdown",
        )


async def mysubs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mysubs command - View user subscriptions."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    subscriptions = get_user_subscriptions(user_id)

    if not subscriptions:
        await update.message.reply_text(
            "📚 *اشتراكاتي*\n\n"
            "أنت غير مشترك في أي مواد حالياً.\n"
            "يمكنك الاشتراك في أي مادة لعرض تفاصيلها والضغط على زر 📢 اشتراك.",
            parse_mode="Markdown",
        )
        return

    lines = ["📢 *اشتراكاتي:*\n"]
    keyboard = []

    for sub in subscriptions:
        subject = sub.get("subjects", {})
        subject_id = sub.get("subject_id")
        if not subject_id:
            continue
        subject_name = (
            (subject.get("name", "غير معروف") or "مادة")
            .replace("*", "")
            .replace("_", "")[:25]
        )
        lines.append(f"• 📚 {subject_name}")
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📚 {subject_name}{'...' if len(subject.get('name', '')) > 25 else ''}",
                    callback_data=f"subject_{subject_id}",
                )
            ]
        )

    if not keyboard:
        await update.message.reply_text(
            "📢 *اشتراكاتي*\n\nأنت غير مشترك في أي مواد.",
            parse_mode="Markdown",
        )
        return

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def unread_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unread command - View unread files."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    unread_files = get_unread_files_for_user(user_id)

    if not unread_files:
        await update.message.reply_text(
            "✅ *ملفاي غير المقروءة*\n\nلا توجد ملفات غير مقروءة لديك. أحسنت!",
            parse_mode="Markdown",
        )
        return

    # Group by subject
    by_subject = {}
    for f in unread_files:
        subj = f.get("subjects", {})
        subj_name = subj.get("name", "غير معروف")
        if subj_name not in by_subject:
            by_subject[subj_name] = []
        by_subject[subj_name].append(f)

    lines = ["🆕 *الملفات غير المقروءة:*\n"]
    keyboard = []

    for subj_name, files in by_subject.items():
        safe_subj_name = subj_name.replace("*", "").replace("_", "")
        lines.append(f"\n📚 {safe_subj_name} ({len(files)} ملفات)")
        for f in files[:3]:  # Show first 3 files per subject
            safe_name = (
                f["name"].replace("*", "").replace("_", "") if f.get("name") else "ملف"
            )
            lines.append(f"  • 📄 {safe_name}")
        if len(files) > 3:
            lines.append(f"  ... و{len(files) - 3} ملفات أخرى")

    keyboard.append(
        [InlineKeyboardButton("📚 عرض جميع المواد", callback_data="back_main")]
    )

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /favorites command - View user favorites."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    favorites = get_user_favorites(user_id)

    if not favorites:
        await update.message.reply_text(
            "⭐ *المفضلة*\n\n"
            "لا توجد ملفات مفضلة لديك.\n"
            "يمكنك إضافة ملفات للمفضلة عند عرض أي ملف.",
            parse_mode="Markdown",
        )
        return

    lines = ["⭐ *ملفاتي المفضلة:*\n"]
    keyboard = []

    for fav in favorites:
        file_obj = fav.get("files", {})
        file_id = file_obj.get("id")
        if not file_id:
            continue
        file_name = file_obj.get("name", "غير معروف") or "ملف"
        safe_name = file_name.replace("*", "").replace("_", "")[:30]
        lines.append(f"• 📄 {safe_name}")
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📄 {safe_name}{'...' if len(file_name) > 30 else ''}",
                    callback_data=f"file_{file_id}",
                )
            ]
        )

    if not keyboard:
        await update.message.reply_text(
            "⭐ *المفضلة*\n\nلا توجد ملفات مفضلة.",
            parse_mode="Markdown",
        )
        return

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mystats command - View user personal statistics."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if _maintenance_enabled() and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    # Get user stats
    stats = get_user_file_stats(user_id)
    viewed_count = stats["viewed_count"]

    # Get subscriptions count
    subscriptions = get_user_subscriptions(user_id)
    subs_count = len(subscriptions)

    # Get favorites count
    favorites = get_user_favorites(user_id)
    favs_count = len(favorites)

    # Get questions asked
    limit_info = get_user_question_limit(user_id)
    questions_asked = limit_info["questions_asked"]

    lines = [
        "📊 *إحصائياتي الشخصية*\n",
        f"📄 الملفات المقروءة: *{viewed_count}*",
        f"📚 المواد المشتركة: *{subs_count}*",
        f"⭐ الملفات المفضلة: *{favs_count}*",
        f"❓ الأسئلة المرسلة: *{questions_asked}* من 3",
    ]

    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def answer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /answer command - Admin reply to Ask Me questions."""
    user_id = update.message.from_user.id
    save_user(update.message.from_user)

    if not is_admin(user_id):
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 *استخدم الأمر هكذا:*\n"
            "`/answer <رقم السؤال> <الإجابة>`\n\n"
            "مثال: `/answer 5 الإجابة على سؤالك هي...`",
            parse_mode="Markdown",
        )
        return

    try:
        question_id = int(context.args[0])
        answer_text = " ".join(context.args[1:])

        # Get the question
        question = get_question_by_id(question_id)
        if not question:
            await update.message.reply_text("❌ السؤال غير موجود.")
            return

        # Answer the question
        answer_question(question_id, answer_text, user_id)
        log_activity(update.message.from_user, "answer_question", f"Q:{question_id}")

        # Send answer to the student
        student_id = question["user_id"]
        try:
            await context.bot.send_message(
                chat_id=student_id,
                text=(
                    f"💬 *إجابة على سؤالك:*\n\n"
                    f"❓ السؤال: {question['question']}\n\n"
                    f"💬 الإجابة: {answer_text}\n\n"
                    "👨‍💻 فريق الإدارة"
                ),
                parse_mode="Markdown",
            )
            await update.message.reply_text(f"✅ تم إرسال الإجابة للطالب بنجاح.")
        except Exception as e:
            logger.error(f"Failed to send answer to student {student_id}: {e}")
            await update.message.reply_text(
                "⚠️ تم حفظ الإجابة ولكن تعذر إرسالها للطالب."
            )
    except ValueError:
        await update.message.reply_text("⚠️ رقم السؤال يجب أن يكون رقماً.")
    except Exception as e:
        logger.error(f"Error in answer_command: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة الرد.")


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        save_user(update.message.from_user)
        uid = update.message.from_user.id

        if _maintenance_enabled() and not is_admin(uid):
            await update.message.reply_text(
                "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
            )
            return

        if context.user_data.get("awaiting_broadcast_message"):
            if not admin_can(uid, "broadcast"):
                context.user_data.pop("awaiting_broadcast_message", None)
                await update.message.reply_text("⛔ غير مصرح.")
                return
            context.user_data.pop("awaiting_broadcast_message", None)
            payload = _extract_broadcast_payload(update.message)
            if not payload:
                await update.message.reply_text(
                    "⚠️ لم يتم التعرف على محتوى الإذاعة. أرسل نصاً أو ملفاً صالحاً."
                )
                return
            enqueue_broadcast(payload, uid)
            log_activity(
                update.message.from_user, "broadcast_queued", payload.get("kind")
            )
            await update.message.reply_text(
                "✅ تمت إضافة الإذاعة إلى قائمة الإرسال وسيتم إرسالها تلقائياً."
            )
            return

        # ── Waiting for Ask Me question (File/Photo) ──────────────────────────────
        if context.user_data.get("awaiting_ask_question"):
            try:
                caption = (update.message.caption or "").strip()
                file_id, file_name, file_type = get_file_from_message(update.message)

                if not file_id:
                    await update.message.reply_text("⚠️ لم يتم التعرف على الملف.")
                    return

                text_for_db = f"[File: {file_name}] {caption}".strip()

                # Create the question in DB
                question = create_ask_me_question(uid, text_for_db)
                if question:
                    log_activity(
                        update.message.from_user, "ask_me_question_file", file_type
                    )
                    context.user_data.pop("awaiting_ask_question", None)

                    # Notify admins
                    admins = get_admins()
                    admin_ids = [a["id"] for a in admins]
                    if OWNER_ID not in admin_ids:
                        admin_ids.append(OWNER_ID)

                    user_info = update.message.from_user
                    username = (
                        f"@{user_info.username}"
                        if user_info.username
                        else "بدون اسم مستخدم"
                    )
                    esc_username = escape_markdown(username, version=1)
                    esc_caption = (
                        escape_markdown(caption, version=1) if caption else "بدون وصف"
                    )

                    notification = (
                        f"📩 *سؤال جديد (ملف) من طالب*\n"
                        f"━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 User: {esc_username}\n"
                        f"🆔 ID: `{uid}`\n\n"
                        f"📁 النوع: {file_type}\n"
                        f"📝 الوصف: {esc_caption}\n\n"
                        f"──────────────────\n"
                        f"💡 *للرد:* اضغط Reply (رد) على هذه الرسالة واكتب الإجابة"
                    )

                    for admin_id in admin_ids:
                        try:
                            # First send the notification text
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=notification,
                                parse_mode="Markdown",
                            )
                            # Then send the actual file
                            await send_file_by_type(
                                context.bot,
                                admin_id,
                                file_id,
                                file_type,
                                caption=f"سؤال من {username}",
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to notify admin {admin_id} about file question: {e}"
                            )

                    remaining = get_remaining_questions(uid)
                    await update.message.reply_text(
                        "✅ *تم إرسال ملفك للإدارة كسؤال*\n\n"
                        f"⚠️ المتبقي لديك: *{remaining}* أسئلة فقط\n\n"
                        "💬 سيقوم فريق الإدارة بالرد عليك مباشرة في المحادثة الخاصة.",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        "❌ حدث خطأ أثناء إرسال السؤال. حاول مرة أخرى."
                    )
            except Exception as e:
                logger.error(f"Error in handle_file (Ask Me): {e}")
                await update.message.reply_text(
                    "❌ حدث خطأ غير متوقع أثناء إرسال الملف."
                )
            return

        if not admin_can(uid, "upload_files"):
            await update.message.reply_text(
                f"⛔ رفع الملفات للمشرفين فقط.\n👨‍💻 {DEVELOPER}"
            )
            return

        file_id, file_name, file_type = get_file_from_message(update.message)
        if not file_id:
            return
        log_activity(update.message.from_user, "upload_file", file_name)

        # Get file size
        try:
            file_obj = await context.bot.get_file(file_id)
            file_size = file_obj.file_size
        except Exception as e:
            logger.warning(f"Could not retrieve file size for {file_name}: {e}")
            file_size = None

        pending_files = context.user_data.get("pending_files") or []
        pending_files.append(
            {
                "file_id": file_id,
                "file_name": file_name,
                "file_type": file_type,
                "message_id": update.message.message_id,
                "file_size": file_size,
            }
        )
        context.user_data["pending_files"] = pending_files

        category_id = context.user_data.get("pending_category_id")
        if category_id:
            subjects = get_subjects(category_id)
            if subjects:
                await update.message.reply_text(
                    f"📎 تم استلام *{len(pending_files)}* ملف/ملفات.\n\n📁 اختر المادة لحفظ الملفات:",
                    reply_markup=build_category_subjects_keyboard(
                        category_id,
                        subjects,
                        uid,
                        include_add_new=True,
                        for_upload=True,
                    ),
                    parse_mode="Markdown",
                )
                return

        categories = get_categories()
        if not categories:
            # No categories exist, guide admin to create first category
            keyboard = [
                [InlineKeyboardButton("➕ إنشاء أول قسم", callback_data="new_category")]
            ]
            await update.message.reply_text(
                f"📎 تم استلام *{len(pending_files)}* ملف/ملفات.\n\n"
                "📚 لا توجد أقسام بعد. يرجى إنشاء أول قسم أولاً:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return

        keyboard = [
            [InlineKeyboardButton(f"📚 {c['name']}", callback_data=f"cat_{c['id']}")]
            for c in categories
        ]
        await update.message.reply_text(
            f"📎 تم استلام *{len(pending_files)}* ملف/ملفات.\n\n📚 اختر القسم أولًا:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Critical error in handle_file: {e}")
        try:
            await update.message.reply_text("❌ حدث خطأ غير متوقع في معالجة الملف.")
        except:
            pass


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = update.message.from_user.id
        save_user(update.message.from_user)

        if is_user_banned(uid):
            return

        if _maintenance_enabled() and not is_admin(uid):
            await update.message.reply_text(
                "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
            )
            return

        text = (update.message.text or "").strip()

        # Check if this is a group message and handle appropriately
        if (
            update.message.chat.type == "group"
            or update.message.chat.type == "supergroup"
        ):
            # For group messages, we might want to ignore certain commands or handle differently
            # For now, we'll let the normal flow handle it

            # If it's a command, let it be processed normally
            if text.startswith("/"):
                # Commands in groups should be handled normally
                pass
            else:
                # For non-command text in groups, we might want to ignore or respond
                # For now, we'll let it go through normal processing
                pass

        # ── Check if echo mode is enabled ───────────────────────────────────────────
        if context.user_data.get("echo_mode_enabled", False):
            # In echo mode, just repeat back what the user sent
            await update.message.reply_text(text)
            return

        keyboard_actions = {
            "📁 الملفات": archive_command,
            "🔍 بحث": search_command,
            "📢 اشتراكاتي": mysubs_command,
            "⭐ المفضلة": favorites_command,
            "🆕 غير مقروءة": unread_command,
            "📊 إحصائياتي": mystats_command,
            "❓ سؤال للإدارة": ask_command,
            "🤖 مهندس الذكاء": ai_engineer_command,
        }

        if text in keyboard_actions:
            try:
                handler = keyboard_actions[text]
                await handler(update, context)
            except Exception as e:
                logger.error(f"Error in keyboard action {text}: {e}")
                await update.message.reply_text(
                    f"❌ حدث خطأ أثناء تنفيذ الأمر. يرجى المحاولة لاحقاً.\nخطأ: {str(e)[:100]}"
                )
            return

        if text == "🛠 لوحة الأدمن":
            if is_admin(uid):
                try:
                    await send_panel(update.message, uid)
                except Exception as e:
                    logger.error(f"Error in admin panel: {e}", exc_info=True)
                    await update.message.reply_text(
                        f"❌ حدث خطأ في لوحة الإدارة.\n{str(e)[:100]}"
                    )
            else:
                await update.message.reply_text("⛔ هذا الخيار للمشرفين فقط.")
            return

        if text == "🔗 خدماتنا":
            try:
                links = get_service_links()
                if links:
                    keyboard = []
                    for link in links:
                        keyboard.append(
                            [
                                InlineKeyboardButton(
                                    f"{link.get('icon', '🔗')} {link.get('name', 'رابط')}",
                                    url=link.get("url", "https://t.me/"),
                                )
                            ]
                        )
                    keyboard.append(
                        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
                    )
                    await update.message.reply_text(
                        "🔗 **خدماتنا**\n\nاختر من الروابط التالية:",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        "🔗 **خدماتنا**\n\n\nلا توجد روابط متوفرة حالياً.",
                        parse_mode="Markdown",
                    )
            except Exception as e:
                logger.error(f"Error in services: {e}")
                await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة لاحقاً.")
            return

        if text == "🔙 الرئيسية":
            try:
                await start(update, context)
            except Exception as e:
                logger.error(f"Error in main menu: {e}")
                await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة لاحقاً.")
            return

        if is_admin(uid) and (text == "🔧 تفعيل الصيانة" or text == "🟢 إيقاف الصيانة"):
            current = _is_maintenance_enabled()
            _set_maintenance_mode(not current)
            status = "مفعّل ✅" if not current else "معطّل ❌"
            await update.message.reply_text(
                f"🔧 تم {'تفعيل' if not current else 'إيقاف'} وضع الصيانة: {status}"
            )
            await send_panel(update.message, uid)
            return

        if is_admin(uid) and text == "📁 الملفات":
            await archive_command(update, context)
            return

        # Handle admin panel keyboard buttons (Reply Keyboard)
        if is_admin(uid):
            if text == "📊 الإحصائيات":
                subjects = get_subjects_with_file_counts()
                total_files = 0
                for s in subjects:
                    files = s.get("files") or []
                    if (
                        isinstance(files, list)
                        and files
                        and isinstance(files[0], dict)
                        and "count" in files[0]
                    ):
                        total_files += files[0]["count"] or 0
                total_users = len(get_all_users())
                lines = [
                    "📊 *الإحصائيات*\n━━━━━━━━━━━━━━━━━━━\n",
                    f"👥 المستخدمون: *{total_users}*",
                    f"📚 المواد: *{len(subjects)}*",
                    f"📄 الملفات: *{total_files}*\n",
                ]
                if subjects:
                    lines.append("📁 تفاصيل المواد:")
                    categories = {c.get("id"): c.get("name") for c in get_categories()}
                    for s in subjects:
                        files = s.get("files") or []
                        cnt = 0
                        if (
                            isinstance(files, list)
                            and files
                            and isinstance(files[0], dict)
                            and "count" in files[0]
                        ):
                            cnt = files[0]["count"] or 0
                        cat_name = (
                            (categories.get(s.get("category_id")) or "")
                            .replace("*", "")
                            .replace("_", "")
                        )
                        subj_name = (
                            (s.get("name") or "غير معروف")
                            .replace("*", "")
                            .replace("_", "")
                        )
                        label = f"{cat_name} / {subj_name}" if cat_name else subj_name
                        lines.append(f"  • {label}: {cnt} ملف")
                await update.message.reply_text(
                    "\n".join(lines),
                    reply_markup=get_admin_panel_keyboard(uid),
                    parse_mode="Markdown",
                )
                return

            if text == "👥 عرض المستخدمين":
                if not admin_can(uid, "view_users"):
                    await update.message.reply_text("⛔ غير مصرح.")
                    return
                text, kb = build_users_page_text_and_keyboard(page=1)
                await update.message.reply_text(
                    text, reply_markup=kb, parse_mode="Markdown"
                )
                return

            if text.startswith("adm_users_"):
                if not admin_can(uid, "view_users"):
                    await update.message.reply_text("⛔ غير مصرح.")
                    return
                try:
                    page = int(text.split("_")[2])
                except Exception:
                    page = 1
                text, kb = build_users_page_text_and_keyboard(page=page)
                await update.message.reply_text(
                    text, reply_markup=kb, parse_mode="Markdown"
                )
                return

            if text == "📈 نشاط المستخدمين":
                if not admin_can(uid, "view_activity"):
                    await update.message.reply_text("⛔ غير مصرح.")
                    return
                text, kb = build_activity_page_text_and_keyboard(page=1)
                await update.message.reply_text(
                    text, reply_markup=kb, parse_mode="Markdown"
                )
                return

            if text.startswith("adm_activity_"):
                if not admin_can(uid, "view_activity"):
                    await update.message.reply_text("⛔ غير مصرح.")
                    return
                try:
                    page = int(text.split("_")[2])
                except Exception:
                    page = 1
                text, kb = build_activity_page_text_and_keyboard(page=page)
                await update.message.reply_text(
                    text, reply_markup=kb, parse_mode="Markdown"
                )
                return

            if "أسئلة الطلاب" in text:
                questions = get_all_pending_questions()
                lines = ["❓ *أسئلة الطلاب*\n━━━━━━━━━━━━━━━━━━━\n"]
                if not questions:
                    lines.append("لا توجد أسئلة قيد الانتظار.")
                else:
                    for q in questions:
                        user = q.get("users") or {}
                        username = (
                            f"@{user.get('username')}"
                            if user.get("username")
                            else user.get("first_name") or "مجهول"
                        )
                        user_id_q = user.get("id", "?")
                        question_text = (
                            q["question"][:40] + "..."
                            if len(q["question"]) > 40
                            else q["question"]
                        )
                        lines.append(f"• {username} (ID:{user_id_q})")
                        lines.append(f"  _{question_text}_")
                        lines.append(f"  [/answer {q['id']}]")
                        lines.append("")
                lines.append("\nللرد: أرسل `/answer <رقم السؤال> <الإجابة>`")
                kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
                await update.message.reply_text(
                    "\n".join(lines),
                    reply_markup=kb,
                    parse_mode="Markdown",
                )
                return

            if "طلبات الملفات" in text:
                try:
                    requests = get_all_pending_file_requests()
                except Exception as e:
                    logger.error(f"Error fetching file requests: {e}")
                    await update.message.reply_text(
                        "⚠️ جدول طلبات الملفات غير موجود.\nيرجى إنشائه في Supabase.",
                        reply_markup=get_admin_panel_keyboard(uid),
                    )
                    return
                lines = ["📄 *طلبات الملفات*\n━━━━━━━━━━━━━━━━━━━\n"]
                if not requests:
                    lines.append("لا توجد طلبات قيد الانتظار.")
                else:
                    for req in requests:
                        user = req.get("users") or {}
                        username = (
                            f"@{user.get('username')}"
                            if user.get("username")
                            else user.get("first_name") or "مجهول"
                        )
                        lines.append(f"• {username}")
                        lines.append(f"  📝 {req['request_text']}")
                        lines.append(f"  [/fulfill_{req['id']}] [/reject_{req['id']}]")
                        lines.append("")
                lines.append(
                    "\n💡 للأخذ: `/fulfill_رقم_الطلب`\n❌ للرفض: `/reject_رقم_الطلب <السبب>`"
                )
                kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
                await update.message.reply_text(
                    "\n".join(lines),
                    reply_markup=kb,
                    parse_mode="Markdown",
                )
                return

            if text == "👥 إدارة الأدمنز":
                if not admin_can(uid, "manage_admins"):
                    await update.message.reply_text("⛔ غير مصرح.")
                    return
                admins = get_admins()
                lines = ["👥 *إدارة الأدمنز*\n━━━━━━━━━━━━━━━━━━━\n"]
                if admins:
                    for a in admins:
                        label = _format_user_label_md(a)
                        lines.append(f"• {label} (ID:{a['id']})")
                else:
                    lines.append("لا يوجد أدمنز مضافون بعد.")
                lines.append(
                    "\n_لإضافة أدمن: أرسل معرفه الرقمي بعد الضغط على زر الإضافة_"
                )
                kb = [
                    [
                        InlineKeyboardButton(
                            "➕ إضافة أدمن", callback_data="adm_add_admin"
                        )
                    ],
                ]
                if admins:
                    for a in admins:
                        name = a["first_name"] or str(a["id"])
                        kb.append(
                            [
                                InlineKeyboardButton(
                                    f"🗑 حذف {name}",
                                    callback_data=f"adm_del_admin_{a['id']}",
                                )
                            ]
                        )
                kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")])
                await update.message.reply_text(
                    "\n".join(lines),
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode="Markdown",
                )
                return

            if text == "⚙️ صلاحيات الأدمنز":
                if not is_owner(uid):
                    await update.message.reply_text("⛔ للمالك فقط.")
                    return
                admins = [a for a in get_admins() if a.get("id") != OWNER_ID]
                lines = ["⚙️ *صلاحيات الأدمنز*\nاختر أدمن للتعديل:"]
                kb = []
                if admins:
                    for a in admins:
                        label = _format_user_label_plain(a)
                        kb.append(
                            [
                                InlineKeyboardButton(
                                    f"{label} (ID:{a['id']})",
                                    callback_data=f"perm_admin_{a['id']}",
                                )
                            ]
                        )
                else:
                    lines.append("لا يوجد أدمنز لإدارة صلاحياتهم.")
                kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")])
                await update.message.reply_text(
                    "\n".join(lines),
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode="Markdown",
                )
                return

            if text == "📢 إرسال إذاعة":
                if not admin_can(uid, "broadcast"):
                    await update.message.reply_text("⛔ غير مصرح.")
                    return
                users = get_all_users()
                await update.message.reply_text(
                    f"📢 *إرسال إذاعة*\n\n"
                    f"👥 المستخدمون: *{len(users)}*\n\n"
                    "✍️ أرسل رسالتك الآن (نص أو أي ملف) وسيتم إدرجها في قائمة الإذاعة:",
                    parse_mode="Markdown",
                )
                context.user_data["awaiting_broadcast_message"] = True
                return

        # ── Check if this is a reply to an Ask Me question (Admin Response) ───────
        if update.message.reply_to_message and is_admin(uid):
            replied_msg = update.message.reply_to_message
            # Check if the replied message is an Ask Me notification
            if replied_msg.text and "📩 سؤال جديد من طالب" in replied_msg.text:
                # Extract user ID from the message
                import re

                id_match = re.search(r"🆔 ID: (\d+)", replied_msg.text)
                if id_match:
                    student_id = int(id_match.group(1))
                    question_text = ""
                    # Extract question text (everything after "❓ السؤال:")
                    if "❓ السؤال:" in replied_msg.text:
                        question_text = replied_msg.text.split("❓ السؤال:")[1].strip()

                    # Send the reply to the student
                    try:
                        await context.bot.send_message(
                            chat_id=student_id,
                            text=(
                                f"💬 *رد الإدارة على سؤالك:*\n\n"
                                f"{text}\n\n"
                                f"👨‍💻 فريق الإدارة"
                            ),
                            parse_mode="Markdown",
                        )
                        await update.message.reply_text("✅ تم إرسال ردك للطالب بنجاح!")
                        log_activity(
                            update.message.from_user,
                            "answer_ask_me",
                            f"to:{student_id}",
                        )

                        # Mark question as answered (if we can find it)
                        try:
                            questions = get_user_pending_questions(student_id)
                            if questions:
                                # Get the most recent pending question
                                for q in questions:
                                    if (
                                        q["status"] == "pending"
                                        and question_text
                                        and question_text[:20] in q["question"]
                                    ):
                                        answer_question(q["id"], text, uid)
                                        break
                        except Exception:
                            pass  # Don't fail if we can't update the question status

                        return
                    except Exception as e:
                        logger.error(
                            f"Failed to send admin reply to student {student_id}: {e}"
                        )
                        await update.message.reply_text("⚠️ تعذر إرسال الرد للطالب.")
                        return

        # ── Waiting for Ask Me question ───────────────────────────────────────────
        if context.user_data.get("awaiting_ask_question"):
            try:
                if not text:
                    await update.message.reply_text("⚠️ السؤال لا يمكن أن يكون فارغاً.")
                    return

                # Create the question
                question = create_ask_me_question(uid, text)
                if question:
                    log_activity(
                        update.message.from_user, "ask_me_question", text[:100]
                    )
                    context.user_data.pop("awaiting_ask_question", None)

                    # Notify admins
                    admins = get_admins()
                    admin_ids = [a["id"] for a in admins]
                    if OWNER_ID not in admin_ids:
                        admin_ids.append(OWNER_ID)

                    user_info = update.message.from_user
                    username = (
                        f"@{user_info.username}"
                        if user_info.username
                        else "بدون اسم مستخدم"
                    )

                    # Escape for Markdown V1
                    esc_username = escape_markdown(username, version=1)
                    esc_text = escape_markdown(text, version=1)

                    notification = (
                        f"📩 *سؤال جديد من طالب*\n"
                        f"━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 User: {esc_username}\n"
                        f"🆔 ID: `{uid}`\n\n"
                        f"❓ السؤال:\n{esc_text}\n\n"
                        f"──────────────────\n"
                        f"💡 *للرد:* اضغط Reply (رد) على هذه الرسالة واكتب الإجابة"
                    )

                    for admin_id in admin_ids:
                        try:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=notification,
                                parse_mode="Markdown",
                            )
                        except Exception as e:
                            logger.warning(f"Failed to notify admin {admin_id}: {e}")

                    remaining = get_remaining_questions(uid)
                    await update.message.reply_text(
                        "✅ *تم إرسال سؤالك للإدارة*\n\n"
                        f"⚠️ المتبقي لديك: *{remaining}* أسئلة فقط\n\n"
                        "💬 سيقوم فريق الإدارة بالرد عليك مباشرة في المحادثة الخاصة.\n\n"
                        "📌 *ملاحظة:*\n"
                        "أثناء وضع Ask Me لن تظهر قائمة المواد أو الأقسام حتى تنتهي من الأسئلة أو تقوم بإنهاء المحادثة.",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        "❌ حدث خطأ أثناء إرسال السؤال. حاول مرة أخرى."
                    )
            except Exception as e:
                logger.error(f"Error in handle_text (Ask Me): {e}")
                await update.message.reply_text(
                    "❌ حدث خطأ غير متوقع. يرجى المحاولة لاحقاً."
                )
            return

        # ── Waiting for AI question ────────────────────────────────────────────────
        if context.user_data.get("awaiting_ai_question"):
            if not text:
                await update.message.reply_text("⚠️ السؤال لا يمكن أن يكون فارغاً.")
                return

            context.user_data.pop("awaiting_ai_question", None)
            await update.message.reply_text("🤖 جاري التفكير... ⏳")

            try:
                response = await ask_ai(text)
                log_activity(update.message.from_user, "ai_question", text[:50])

                await update.message.reply_text(f"🤖 *الإجابة:*\n\n{response}")

                keyboard = get_topic_keyboard()
                await update.message.reply_text(
                    "❓ هل لديك سؤال آخر؟", reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Error in handle_text (AI): {e}")
                await update.message.reply_text(
                    "❌ حدث خطأ في الإجابة على سؤالك. يرجى المحاولة لاحقاً."
                )
            return

        # ── Waiting for broadcast message ─────────────────────────────────────────
        if context.user_data.get("awaiting_broadcast_message"):
            if not admin_can(uid, "broadcast"):
                context.user_data.pop("awaiting_broadcast_message", None)
                await update.message.reply_text("⛔ غير مصرح.")
                return
            context.user_data.pop("awaiting_broadcast_message", None)
            payload = _extract_broadcast_payload(update.message)
            if not payload:
                await update.message.reply_text(
                    "⚠️ لم يتم التعرف على محتوى الإذاعة. أرسل نصاً أو ملفاً صالحاً."
                )
                return
            enqueue_broadcast(payload, uid)
            log_activity(
                update.message.from_user, "broadcast_queued", payload.get("kind")
            )
            await update.message.reply_text(
                "✅ تمت إضافة الإذاعة إلى قائمة الإرسال وسيتم إرسالها تلقائياً."
            )
            return

        # ── Waiting for admin ID to add ───────────────────────────────────────────
        if context.user_data.get("awaiting_admin_id"):
            if not admin_can(uid, "manage_admins"):
                context.user_data.pop("awaiting_admin_id", None)
                await update.message.reply_text("⛔ غير مصرح.")
                return
            context.user_data.pop("awaiting_admin_id", None)
            if not text.lstrip("-").isdigit():
                await update.message.reply_text("⚠️ أرسل رقم ID صحيح فقط.")
                return
            new_admin_id = int(text)
            if new_admin_id == OWNER_ID:
                await update.message.reply_text("⚠️ هذا المالك بالفعل.")
                return
            if is_admin_in_db(new_admin_id):
                await update.message.reply_text("⚠️ هذا الشخص أدمن بالفعل.")
                return
            try:
                add_admin(new_admin_id, None, f"ID:{new_admin_id}")
                log_activity(update.message.from_user, "add_admin", str(new_admin_id))
                await update.message.reply_text(
                    f"✅ تم إضافة الأدمن بنجاح.\n🆔 `{new_admin_id}`\n\n"
                    "📌 سيتمكن الآن من رفع الملفات وإنشاء مواد.",
                    parse_mode="Markdown",
                )
                await send_panel(update.message, update.message.from_user.id)
                return
            except Exception as exc:
                logger.exception(
                    "Failed to add admin: %s", _format_supabase_error(exc), exc_info=exc
                )
                await update.message.reply_text(
                    "❌ حدث خطأ أثناء إضافة الأدمن. تأكد من الاتصال وقاعدة البيانات ثم حاول مرة أخرى."
                )
                return

        # ── Waiting for category name ───────────────────────────────────────────
        if context.user_data.get("awaiting_category_name"):
            if not is_admin(uid):
                context.user_data.pop("awaiting_category_name", None)
                await update.message.reply_text("⛔ غير مصرح.")
                return
            category_name = update.message.text.strip()
            if not category_name:
                await update.message.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
                return
            context.user_data.pop("awaiting_category_name", None)

            # Create the category
            try:
                supabase.table("categories").upsert(
                    {"name": category_name}, on_conflict="name"
                ).execute()
                _invalidate_categories_cache()
                await update.message.reply_text(
                    f"✅ تم إنشاء القسم *{category_name}* بنجاح!", parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error creating category: {e}")
                await update.message.reply_text("❌ حدث خطأ أثناء إنشاء القسم.")

            await send_archive(update.message, user_id=uid)
            return

        # ── Waiting for subject name ───────────────────────────────────────────
        if context.user_data.get("awaiting_subject_name"):
            if not admin_can(uid, "manage_subjects"):
                context.user_data.pop("awaiting_subject_name", None)
                await update.message.reply_text("⛔ غير مصرح.")
                return
            subject_name = update.message.text.strip()
            if not subject_name:
                await update.message.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
                return
            pending_files = context.user_data.get("pending_files") or []
            category_id = context.user_data.get("pending_category_id")
            context.user_data.clear()

            subject_id = create_subject(subject_name, category_id=category_id)
            log_activity(update.message.from_user, "create_subject", subject_name)

            if pending_files and subject_id:
                saved = 0
                for pf in pending_files:
                    fwd = await forward_to_archive(
                        context,
                        update.message.chat_id,
                        pf["message_id"],
                        update.message,
                    )
                    if not fwd:
                        continue
                    save_file(
                        pf["file_name"],
                        pf["file_id"],
                        pf["file_type"],
                        subject_id,
                        fwd.message_id,
                    )
                    log_activity(
                        update.message.from_user, "add_file_to_subject", pf["file_name"]
                    )
                    saved += 1
                await update.message.reply_text(
                    f"✅ تم إنشاء *{subject_name}* وحفظ *{saved}* ملف/ملفات!",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(
                    f"✅ تم إنشاء مادة *{subject_name}*!", parse_mode="Markdown"
                )

            await send_archive(update.message, user_id=uid)
            return

        if not is_admin(uid):
            await send_archive(update.message, user_id=uid)
            return

        await update.message.reply_text("📎 أرسل ملفاً لرفعه، أو /panel للوحة الإدارة.")
    except Exception as e:
        logger.error(f"Critical error in handle_text: {e}")
        try:
            await update.message.reply_text("❌ حدث خطأ غير متوقع في معالجة طلبك.")
        except:
            pass


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if is_user_banned(user_id):
        return

    if _maintenance_enabled() and not is_admin(user_id):
        await query.message.reply_text(
            "🛠️ البوت حالياً في وضع الصيانة. يرجى المحاولة لاحقاً."
        )
        return

    if data == "about_dev":
        log_activity(query.from_user, "about")
        await query.message.reply_text(ABOUT_DEV_TEXT, parse_mode="Markdown")
        return
    if data == "show_commands":
        log_activity(query.from_user, "commands")
        await query.message.reply_text(COMMANDS_TEXT, parse_mode="Markdown")
        return
    if data == "about_bot":
        log_activity(query.from_user, "about_bot")
        await query.message.reply_text(ABOUT_DEV_TEXT, parse_mode="Markdown")
        return

    # Handle link approval
    if data == "ignore_link":
        await query.message.edit_text("❌ تم تجاهل الرابط.", reply_markup=None)
        return

    if data.startswith("add_link_"):
        if not admin_can(user_id, "upload_files"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        message_id = int(data.split("_")[2])

        try:
            await context.bot.copy_message(
                chat_id=ARCHIVE_CHANNEL_ID,
                from_chat_id=query.message.chat_id,
                message_id=message_id,
            )
            await query.message.edit_text(
                "✅ تم نسخ الرابط إلى الأرشيف.\n\nالآن اختر القسم والمادة لإضافته:",
                reply_markup=None,
            )
            # Show categories for the admin to choose
            categories = get_categories()
            if categories:
                keyboard = [
                    [
                        InlineKeyboardButton(
                            f"📚 {c['name']}", callback_data=f"cat_{c['id']}"
                        )
                    ]
                    for c in categories
                ]
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="📚 اختر القسم:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="📚 لا توجد أقسام. أنشئ قسمًا أولاً.",
                )
        except Exception as e:
            logger.error(f"Error adding link: {e}")
            await query.message.edit_text("❌ حدث خطأ أثناء إضافة الرابط.")
        return

    if data == "back_start":
        # Show the archive with inline keyboard
        await query.message.edit_text(
            "📁 *الملفات*\n\nاختر القسم لعرض المواد:",
            parse_mode="Markdown",
            reply_markup=build_archive_keyboard(user_id)[0],
        )
        return

    if data == "new_category":
        if not is_admin(user_id):
            await query.answer("⛔ هذا الخيار للمشرفين فقط.", show_alert=True)
            return
        context.user_data["awaiting_category_name"] = True
        await query.message.reply_text(
            "➕ *إضافة قسم جديد*\n\nأرسل اسم القسم الجديد:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 إلغاء", callback_data="back_start")]]
            ),
        )
        return

    if data == "show_archive":
        log_activity(query.from_user, "view_archive")

        # Check if user is in Ask Me typing mode
        if context.user_data.get("awaiting_ask_question") and not is_admin(user_id):
            await query.answer(
                "⚠️ أنت في وضع Ask Me. أرسل سؤالك أو أنهِ المحادثة أولاً.", show_alert=True
            )
            return

        await query.message.edit_text(
            "📁 *الملفات*\n\nاختر القسم لعرض المواد:",
            parse_mode="Markdown",
            reply_markup=build_archive_keyboard(user_id)[0],
        )
        return

    if data == "adm_toggle_maintenance":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        current = _is_maintenance_enabled()
        _set_maintenance_mode(not current)
        status = "مفعّل ✅" if not current else "معطّل ❌"
        await query.answer(
            f"🔧 تم {'تفعيل' if not current else 'إيقاف'} وضع الصيانة: {status}",
            show_alert=True,
        )
        await send_panel(query, user_id, edit=True)
        return

    if data.startswith("cat_"):
        category_id = int(data.split("_")[1])
        category = get_category_by_id(category_id)
        if not category:
            await query.edit_message_text("⚠️ القسم غير موجود.")
            return

        if context.user_data.get("pending_files"):
            context.user_data["pending_category_id"] = category_id
        else:
            context.user_data.pop("pending_category_id", None)

        subjects = get_subjects(category_id)
        pending_files = context.user_data.get("pending_files") or []
        if not subjects:
            kb = [[InlineKeyboardButton("🔙 رجوع للأرشيف", callback_data="back_main")]]
            if admin_can(user_id, "manage_subjects"):
                kb.insert(
                    0,
                    [
                        InlineKeyboardButton(
                            "➕ إنشاء مادة جديدة",
                            callback_data=f"new_subject_{category_id}",
                        )
                    ],
                )
            msg = f"📚 *{category['name']}*\n\nلا توجد مواد بعد."
            if pending_files:
                msg = f"📚 *{category['name']}*\n\nلا توجد مواد بعد. أنشئ مادة لحفظ الملف."
            await query.edit_message_text(
                msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
            )
            return

        if pending_files:
            text = f"📚 *{category['name']}*\n\nاختر المادة لحفظ الملفات:"
        else:
            text = f"📚 *{category['name']}*\n\nاختر المادة لعرض ملفاتها:"
        await query.edit_message_text(
            text,
            reply_markup=build_category_subjects_keyboard(
                category_id,
                subjects,
                user_id,
                include_add_new=True,
                for_upload=bool(pending_files),
            ),
            parse_mode="Markdown",
        )
        return

    # ── View subject ──────────────────────────────────────────────────────────
    if data.startswith("subject_"):
        subject_id = int(data.split("_")[1])
        subject = get_subject_by_id(subject_id)
        if not subject:
            await query.edit_message_text("⚠️ المادة غير موجودة.")
            return
        log_activity(query.from_user, "view_subject", subject.get("name"))
        files = get_files_for_subject(subject_id)

        # Check subscription status
        is_subscribed = is_subscribed_to_subject(user_id, subject_id)
        subs_count = len(get_subscribers_for_subject(subject_id))

        # Build keyboard with subscription button
        keyboard = []
        if files:
            for f in files:
                if admin_can(user_id, "delete_files"):
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                            ),
                            InlineKeyboardButton(
                                "🗑", callback_data=f"del_file_{f['id']}_{subject_id}"
                            ),
                        ]
                    )
                else:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                            )
                        ]
                    )

        # Subscription button
        if is_subscribed:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🔕 إلغاء الاشتراك", callback_data=f"unsubscribe_{subject_id}"
                    )
                ]
            )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "📢 اشتراك", callback_data=f"subscribe_{subject_id}"
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("🔙 رجوع للأرشيف", callback_data="back_main")]
        )

        if admin_can(user_id, "manage_subjects"):
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "🗑 حذف المادة", callback_data=f"del_subject_{subject_id}"
                    )
                ]
            )

        # Get subject stats
        stats = get_subject_stats(subject_id)

        if not files:
            kb_no_files = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]]
            if not is_subscribed:
                kb_no_files.insert(
                    0,
                    [
                        InlineKeyboardButton(
                            "📢 اشتراك", callback_data=f"subscribe_{subject_id}"
                        )
                    ],
                )
            else:
                kb_no_files.insert(
                    0,
                    [
                        InlineKeyboardButton(
                            "🔕 إلغاء الاشتراك",
                            callback_data=f"unsubscribe_{subject_id}",
                        )
                    ],
                )

            msg = (
                f"📂 *{subject['name']}*\n\n"
                f"👥 المشتركين: *{subs_count}*\n"
                f"⭐ التقييم: *{stats['avg_rating']:.1f}* من 5\n\n"
                "لا توجد ملفات بعد."
            )
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(kb_no_files),
                parse_mode="Markdown",
            )
            return

        await query.edit_message_text(
            f"📂 *{subject['name']}*\n\n"
            f"👥 المشتركين: *{subs_count}*\n"
            f"⭐ التقييم: *{stats['avg_rating']:.1f}* من 5\n\n"
            "اختر الملف:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # ── Download file ─────────────────────────────────────────────────────────
    elif data.startswith("file_"):
        file_db_id = int(data.split("_")[1])
        row = get_file_row(file_db_id)
        if not row:
            await query.edit_message_text(
                f"⚠️ الملف غير موجود.\n👨‍💻 {DEVELOPER}", parse_mode="Markdown"
            )
            return

        # Mark file as viewed
        mark_file_as_viewed(user_id, file_db_id)

        log_activity(query.from_user, "download_file", row.get("name"))

        # Check if file is in favorites
        is_fav = is_favorite(user_id, file_db_id)

        # Get file rating
        rating_info = get_file_rating(file_db_id)

        # Build keyboard with favorite and rating buttons
        keyboard = []

        # Favorite button
        fav_label = "⭐ إزالة من المفضلة" if is_fav else "⭐ إضافة للمفضلة"
        keyboard.append(
            [InlineKeyboardButton(fav_label, callback_data=f"toggle_fav_{file_db_id}")]
        )

        # Rating buttons (1-5 stars)
        user_rating = get_user_file_rating(user_id, file_db_id)
        rating_kb = []
        for stars in range(1, 6):
            icon = (
                "⭐"
                if (user_rating and stars <= user_rating) or not user_rating
                else "☆"
            )
            rating_kb.append(
                InlineKeyboardButton(
                    icon, callback_data=f"rate_file_{file_db_id}_{stars}"
                )
            )
        keyboard.append(rating_kb)

        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])

        await send_file_by_type(
            bot=context.bot,
            chat_id=query.message.chat_id,
            file_id=row["file_id"],
            file_type=(row.get("file_type") or "document"),
            caption=(
                f"📁 *{row['subject_name']}*\n"
                f"📄 {row['name']}\n"
                f"⭐ التقييم: *{rating_info['avg']:.1f}* من 5 ({rating_info['count']} تقييم)\n\n"
                f"👨‍💻 {DEVELOPER}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # ── Back to archive ───────────────────────────────────────────────────────
    elif data == "back_main":
        log_activity(query.from_user, "view_archive")
        await send_archive(query, edit=True)

    # ── AI Engineer callbacks ───────────────────────────────────────────────
    elif data.startswith("ai_topic_"):
        topic_key = data.split("_")[2]
        from ai_service import PETROLEUM_TOPICS, get_topic_questions

        topic = PETROLEUM_TOPICS.get(topic_key)
        if not topic:
            await query.answer("⚠️ الموضوع غير موجود.", show_alert=True)
            return

        questions = get_topic_questions(topic_key)
        keyboard = []
        for q in questions:
            keyboard.append(
                [InlineKeyboardButton(q, callback_data=f"ai_q_{topic_key}_{q[:20]}")]
            )
        keyboard.append(
            [InlineKeyboardButton("❓ سؤال حر", callback_data="ai_free_question")]
        )
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_ai_menu")])

        await query.message.edit_text(
            f"🏭 *{topic['ar']}*\n\nاختر سؤالاً أو اطرح سؤالك الخاص:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data == "ai_free_question":
        context.user_data["awaiting_ai_question"] = True
        await query.message.edit_text(
            "🤖 *سؤال للذكاء الاصطناعي*\n\n"
            "اكتب سؤالك في مجال هندسة النفط والغاز:\n\n"
            "⏪ للعودة، اضغط 'رجوع' أو استخدم /start",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data="back_ai_menu")]]
            ),
        )
        return

    elif data == "back_ai_menu":
        keyboard = get_topic_keyboard()
        await query.message.edit_text(
            "🤖 *مهندس الذكاء الاصطناعي*\n\nاختر topic أو اكتب سؤالك مباشرة:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── Subscribe/Unsubscribe ─────────────────────────────────────────────────
    elif data.startswith("subscribe_"):
        subject_id = int(data.split("_")[1])
        try:
            success = subscribe_to_subject(user_id, subject_id)
            if success:
                log_activity(query.from_user, "subscribe_subject", str(subject_id))
                await query.answer("✅ تم الاشتراك بنجاح!", show_alert=True)
            else:
                await query.answer("ℹ️ أنت مشترك بالفعل.", show_alert=True)
        except Exception as e:
            logger.error(f"Error subscribing: {e}")
            await query.answer("❌ حدث خطأ. يرجى المحاولة لاحقاً.", show_alert=True)
            return
        # Refresh the subject view
        subject = get_subject_by_id(subject_id)
        files = get_files_for_subject(subject_id)
        subs_count = len(get_subscribers_for_subject(subject_id))

        keyboard = []
        if files:
            for f in files:
                if admin_can(user_id, "delete_files"):
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                            ),
                            InlineKeyboardButton(
                                "🗑", callback_data=f"del_file_{f['id']}_{subject_id}"
                            ),
                        ]
                    )
                else:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                            )
                        ]
                    )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔕 إلغاء الاشتراك", callback_data=f"unsubscribe_{subject_id}"
                )
            ]
        )
        keyboard.append(
            [InlineKeyboardButton("🔙 رجوع للأرشيف", callback_data="back_main")]
        )

        stats = get_subject_stats(subject_id)
        await query.edit_message_text(
            f"📂 *{subject['name']}*\n\n"
            f"👥 المشتركين: *{subs_count}*\n"
            f"⭐ التقييم: *{stats['avg_rating']:.1f}* من 5\n\n"
            "اختر الملف:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data.startswith("unsubscribe_"):
        subject_id = int(data.split("_")[1])
        try:
            unsubscribe_from_subject(user_id, subject_id)
            log_activity(query.from_user, "unsubscribe_subject", str(subject_id))
            await query.answer("✅ تم إلغاء الاشتراك!", show_alert=True)
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            await query.answer("❌ حدث خطأ. يرجى المحاولة لاحقاً.", show_alert=True)
            return
        # Refresh the subject view
        subject = get_subject_by_id(subject_id)
        files = get_files_for_subject(subject_id)
        subs_count = len(get_subscribers_for_subject(subject_id))

        keyboard = []
        if files:
            for f in files:
                if admin_can(user_id, "delete_files"):
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                            ),
                            InlineKeyboardButton(
                                "🗑", callback_data=f"del_file_{f['id']}_{subject_id}"
                            ),
                        ]
                    )
                else:
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                            )
                        ]
                    )

        keyboard.append(
            [InlineKeyboardButton("📢 اشتراك", callback_data=f"subscribe_{subject_id}")]
        )
        keyboard.append(
            [InlineKeyboardButton("🔙 رجوع للأرشيف", callback_data="back_main")]
        )

        stats = get_subject_stats(subject_id)
        await query.edit_message_text(
            f"📂 *{subject['name']}*\n\n"
            f"👥 المشتركين: *{subs_count}*\n"
            f"⭐ التقييم: *{stats['avg_rating']:.1f}* من 5\n\n"
            "اختر الملف:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # ── Favorites ─────────────────────────────────────────────────────────────
    elif data.startswith("toggle_fav_"):
        file_db_id = int(data.split("_")[2])
        if is_favorite(user_id, file_db_id):
            remove_from_favorites(user_id, file_db_id)
            await query.answer("⭐ تمت الإزالة من المفضلة", show_alert=True)
        else:
            add_to_favorites(user_id, file_db_id)
            await query.answer("⭐ تمت الإضافة للمفضلة", show_alert=True)
        log_activity(query.from_user, "toggle_favorite", str(file_db_id))
        # Go back to file view
        row = get_file_row(file_db_id)
        if row:
            mark_file_as_viewed(user_id, file_db_id)
            is_fav = is_favorite(user_id, file_db_id)
            rating_info = get_file_rating(file_db_id)

            keyboard = []
            fav_label = "⭐ إزالة من المفضلة" if is_fav else "⭐ إضافة للمفضلة"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        fav_label, callback_data=f"toggle_fav_{file_db_id}"
                    )
                ]
            )

            user_rating = get_user_file_rating(user_id, file_db_id)
            rating_kb = []
            for stars in range(1, 6):
                icon = (
                    "⭐"
                    if (user_rating and stars <= user_rating) or not user_rating
                    else "☆"
                )
                rating_kb.append(
                    InlineKeyboardButton(
                        icon, callback_data=f"rate_file_{file_db_id}_{stars}"
                    )
                )
            keyboard.append(rating_kb)
            keyboard.append(
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
            )

            caption_text = (
                f"📁 *{row['subject_name']}*\n"
                f"📄 {row['name']}\n"
                f"⭐ التقييم: *{rating_info['avg']:.1f}* من 5 ({rating_info['count']} تقييم)\n\n"
                f"👨‍💻 {DEVELOPER}"
            )

            if query.message.photo or query.message.video or query.message.document:
                await query.edit_message_caption(
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    text=caption_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )

    elif data.startswith("rate_file_"):
        parts = data.split("_")
        file_db_id = int(parts[2])
        rating = int(parts[3])
        rate_file(user_id, file_db_id, rating)
        log_activity(query.from_user, "rate_file", f"{file_db_id}:{rating}")
        await query.answer(f"⭐ تم التقييم بـ {rating} نجوم!", show_alert=True)
        # Go back to file view
        row = get_file_row(file_db_id)
        if row:
            mark_file_as_viewed(user_id, file_db_id)
            is_fav = is_favorite(user_id, file_db_id)
            rating_info = get_file_rating(file_db_id)

            keyboard = []
            fav_label = "⭐ إزالة من المفضلة" if is_fav else "⭐ إضافة للمفضلة"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        fav_label, callback_data=f"toggle_fav_{file_db_id}"
                    )
                ]
            )

            user_rating = get_user_file_rating(user_id, file_db_id)
            rating_kb = []
            for stars in range(1, 6):
                icon = (
                    "⭐"
                    if (user_rating and stars <= user_rating) or not user_rating
                    else "☆"
                )
                rating_kb.append(
                    InlineKeyboardButton(
                        icon, callback_data=f"rate_file_{file_db_id}_{stars}"
                    )
                )
            keyboard.append(rating_kb)
            keyboard.append(
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
            )

            caption_text = (
                f"📁 *{row['subject_name']}*\n"
                f"📄 {row['name']}\n"
                f"⭐ التقييم: *{rating_info['avg']:.1f}* من 5 ({rating_info['count']} تقييم)\n\n"
                f"👨‍💻 {DEVELOPER}"
            )

            if query.message.photo or query.message.video or query.message.document:
                await query.edit_message_caption(
                    caption=caption_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    text=caption_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )

    # ── Search Menu ───────────────────────────────────────────────────────────
    elif data == "search_menu":
        log_activity(query.from_user, "search_menu")
        await query.edit_message_text(
            "🔍 *البحث عن ملفات*\n\n"
            "للبحث عن أي ملف، أرسل الأمر التالي متبوعاً باسم الملف:\n"
            "`/search اسم_الملف`",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]]
            ),
            parse_mode="Markdown",
        )

    # ── Favorites Menu ────────────────────────────────────────────────────────
    elif data == "favorites_menu":
        log_activity(query.from_user, "favorites_menu")
        favorites = get_user_favorites(user_id)

        valid_favs = [f for f in favorites if f.get("files")]
        if not valid_favs:
            await query.answer("⭐ لا توجد ملفات في المفضلة بعد.", show_alert=True)
            return

        lines = ["⭐ *ملفاتي المفضلة:*\n"]
        keyboard = []
        for fav in valid_favs:
            file_obj = fav.get("files")
            if not file_obj:
                continue

            file_id_db = file_obj.get("id")
            file_name = file_obj.get("name", "غير معروف")
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📄 {file_name}", callback_data=f"file_{file_id_db}"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 رجوع للقائمة الرئيسية", callback_data="back_start"
                )
            ]
        )

        text = "\n".join(lines)
        if query.message.photo:
            await query.edit_message_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    # ── Unread Files Menu ─────────────────────────────────────────────────────
    elif data == "unread_menu":
        log_activity(query.from_user, "unread_menu")
        unread_files = get_unread_files_for_user(user_id)
        if not unread_files:
            await query.answer("✅ لا توجد ملفات غير مقروءة.", show_alert=True)
            return

        lines = ["🆕 *الملفات غير المقروءة:*\n"]
        keyboard = []
        # Show first 10 unread
        for f in unread_files[:10]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"📄 {f['name']}", callback_data=f"file_{f['id']}"
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_start")])
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    # ── My Stats Menu ─────────────────────────────────────────────────────────
    elif data == "mystats_menu":
        log_activity(query.from_user, "mystats_menu")
        stats = get_user_file_stats(user_id)
        viewed_count = stats["viewed_count"]
        favs_count = len(get_user_favorites(user_id))
        subs_count = len(get_user_subscriptions(user_id))

        msg = (
            "📊 *إحصائياتي الشخصية*\n━━━━━━━━━━━━━━━━━━━\n\n"
            f"👁️ ملفات شاهدتها: *{viewed_count}*\n"
            f"⭐ ملفات في المفضلة: *{favs_count}*\n"
            f"📢 اشتراكاتي: *{subs_count}*\n"
        )
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data="back_start")]]
            ),
            parse_mode="Markdown",
        )

    # ── Ask Me Menu ───────────────────────────────────────────────────────────
    elif data == "ask_me_menu":
        log_activity(query.from_user, "ask_me_menu")
        remaining = get_remaining_questions(user_id)
        all_questions = get_user_pending_questions(
            user_id
        )  # This currently gets pending + answered

        lines = ["❓ *Ask Me - تواصل مع الإدارة*\n"]
        lines.append(f"📊 المتبقي من رصيدك: *{remaining}* أسئلة")

        keyboard = []
        if remaining > 0:
            keyboard.append(
                [InlineKeyboardButton("✍️ طرح سؤال جديد", callback_data="ask_me_ask")]
            )

        if all_questions:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "📜 سجل الأسئلة", callback_data="ask_me_my_questions"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 رجوع للقائمة الرئيسية", callback_data="back_main"
                )
            ]
        )

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "ask_me_ask":
        remaining = get_remaining_questions(user_id)
        if remaining <= 0:
            await query.answer(
                "❌ لقد استهلكت الحد المسموح من الأسئلة.", show_alert=True
            )
            return
        context.user_data["awaiting_ask_question"] = True
        await query.edit_message_text(
            "❓ *اسأل الإدارة*\n\n"
            "أنت الآن في وضع طرح الأسئلة. أرسل سؤالك مباشرة (نص أو صورة أو ملف) وسيقوم فريق الإدارة بالرد عليك في أقرب وقت.\n\n"
            f"📊 المتبقي لديك: *{remaining}* أسئلة.\n\n"
            "📌 *ملاحظة:* لا يمكنك تصفح الأرشيف حتى ترسل سؤالك أو تنهي هذا الوضع.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 إلغاء والرجوع", callback_data="ask_me_menu"
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )

    elif data == "ask_me_my_questions":
        pending = get_user_pending_questions(user_id)
        if not pending:
            await query.answer("لا توجد أسئلة قيد الانتظار.", show_alert=True)
            return

        lines = ["📋 *أسئلتي:*\n"]
        for q in pending:
            status_icon = "✅" if q["status"] == "answered" else "⏳"
            lines.append(f"\n{status_icon} {q['question'][:50]}...")
            if q.get("answer"):
                lines.append(f"   💬 الإجابة: {q['answer'][:50]}...")

        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="ask_me_menu")]]
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "ask_me_cancel":
        context.user_data.pop("awaiting_ask_question", None)
        await query.edit_message_text(
            "❌ تم إنهاء وضع طرح الأسئلة.\n\n"
            "يمكنك الآن العودة لاستخدام باقي ميزات البوت.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 رجوع للقائمة الرئيسية", callback_data="back_main"
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )

    elif data == "ask_me_end":
        context.user_data.pop("awaiting_ask_question", None)
        await query.answer("✅ تم إنهاء المحادثة.", show_alert=True)
        await send_archive(query, edit=True)

    # ── New subject (from file flow) ──────────────────────────────────────────
    elif data.startswith("new_subject_"):
        if not admin_can(user_id, "manage_subjects"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        category_id = int(data.split("_")[2])
        category = get_category_by_id(category_id)
        if not category:
            await query.edit_message_text("⚠️ القسم غير موجود.")
            return
        await query.edit_message_text(
            f"✏️ أرسل اسم المادة الجديدة لقسم: *{category['name']}*",
            parse_mode="Markdown",
        )
        context.user_data["awaiting_subject_name"] = True
        context.user_data["pending_category_id"] = category_id
        return

    # ── Add file to subject ───────────────────────────────────────────────────
    elif data.startswith("addto_"):
        if not admin_can(user_id, "upload_files"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        subject_id = int(data.split("_")[1])
        subject = get_subject_by_id(subject_id)
        pending_files = context.user_data.get("pending_files") or []
        if not pending_files:
            await query.edit_message_text("⚠️ لم يتم العثور على ملفات. أعد رفعها.")
            return
        saved = 0
        for pf in pending_files:
            fwd = await forward_to_archive(
                context, query.message.chat_id, pf["message_id"], query.message
            )
            if not fwd:
                continue
            save_file(
                pf["file_name"],
                pf["file_id"],
                pf["file_type"],
                subject_id,
                fwd.message_id,
            )
            log_activity(query.from_user, "add_file_to_subject", pf["file_name"])
            # Notify subscribers about the new file
            await notify_subscribers_of_new_file(
                context.application,
                subject_id,
                pf["file_name"],
                pf["file_id"],
                pf["file_type"],
            )
            saved += 1
        context.user_data.clear()
        await query.edit_message_text(
            f"✅ *تم الحفظ!*\n📄 الملفات: *{saved}*\n📁 *{subject['name']}*",
            parse_mode="Markdown",
        )
        await send_archive(query.message)

    # ── Delete subject ────────────────────────────────────────────────────────
    elif data.startswith("del_subject_"):
        if not admin_can(user_id, "manage_subjects"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        subject_id = int(data.split("_")[2])
        subject = get_subject_by_id(subject_id)
        kb = [
            [
                InlineKeyboardButton(
                    "✅ نعم احذف", callback_data=f"confirm_del_subject_{subject_id}"
                ),
                InlineKeyboardButton("❌ لا", callback_data=f"subject_{subject_id}"),
            ]
        ]
        await query.edit_message_text(
            f"⚠️ حذف *{subject['name']}* وكل ملفاتها؟",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    elif data.startswith("confirm_del_subject_"):
        if not admin_can(user_id, "manage_subjects"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        subject_id = int(data.split("_")[3])
        delete_subject(subject_id)
        log_activity(query.from_user, "delete_subject", str(subject_id))
        await send_archive(query, edit=True)

    # ── Delete file ───────────────────────────────────────────────────────────
    elif data.startswith("del_file_"):
        if not admin_can(user_id, "delete_files"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        parts = data.split("_")
        file_db_id, subject_id = int(parts[2]), int(parts[3])
        kb = [
            [
                InlineKeyboardButton(
                    "✅ نعم احذف",
                    callback_data=f"confirm_del_file_{file_db_id}_{subject_id}",
                ),
                InlineKeyboardButton("❌ لا", callback_data=f"file_{file_db_id}"),
            ]
        ]
        await query.edit_message_text(
            "⚠️ حذف هذا الملف؟", reply_markup=InlineKeyboardMarkup(kb)
        )

    elif data.startswith("confirm_del_file_"):
        if not admin_can(user_id, "delete_files"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        parts = data.split("_")
        file_db_id, subject_id = int(parts[3]), int(parts[4])
        delete_file(file_db_id)
        log_activity(query.from_user, "delete_file", str(file_db_id))
        files = get_files_for_subject(subject_id)
        subject = get_subject_by_id(subject_id)
        if files:
            await query.edit_message_text(
                f"🗑 تم الحذف.\n\n📂 *{subject['name']}*\n\nاختر الملف:",
                reply_markup=build_subject_keyboard(subject_id, files, user_id),
                parse_mode="Markdown",
            )
        else:
            await send_archive(query, edit=True)

    # ── PANEL: stats ──────────────────────────────────────────────────────────
    elif data == "adm_stats":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        log_activity(query.from_user, "view_stats")
        subjects = get_subjects_with_file_counts()
        total_files = 0
        for s in subjects:
            files = s.get("files") or []
            if (
                isinstance(files, list)
                and files
                and isinstance(files[0], dict)
                and "count" in files[0]
            ):
                total_files += files[0]["count"] or 0
        total_users = len(get_all_users())
        lines = [
            "📊 *الإحصائيات*\n━━━━━━━━━━━━━━━━━━━\n",
            f"👥 المستخدمون: *{total_users}*",
            f"📚 المواد: *{len(subjects)}*",
            f"📄 الملفات: *{total_files}*\n",
        ]
        if subjects:
            lines.append("📁 تفاصيل المواد:")
            categories = {c.get("id"): c.get("name") for c in get_categories()}
            for s in subjects:
                files = s.get("files") or []
                cnt = 0
                if (
                    isinstance(files, list)
                    and files
                    and isinstance(files[0], dict)
                    and "count" in files[0]
                ):
                    cnt = files[0]["count"] or 0
                cat_name = (
                    (categories.get(s.get("category_id")) or "")
                    .replace("*", "")
                    .replace("_", "")
                )
                subj_name = (
                    (s.get("name") or "غير معروف").replace("*", "").replace("_", "")
                )
                label = f"{cat_name} / {subj_name}" if cat_name else subj_name
                lines.append(f"  • {label}: {cnt} ملف")
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    elif data == "adm_users":
        if not admin_can(user_id, "view_users"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        log_activity(query.from_user, "view_users")
        text, kb = build_users_page_text_and_keyboard(page=1)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data.startswith("adm_users_"):
        if not admin_can(user_id, "view_users"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        try:
            page = int(data.split("_")[2])
        except Exception:
            page = 1
        text, kb = build_users_page_text_and_keyboard(page=page)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "adm_activity":
        if not admin_can(user_id, "view_activity"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        log_activity(query.from_user, "view_activity")
        text, kb = build_activity_page_text_and_keyboard(page=1)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data.startswith("adm_activity_"):
        if not admin_can(user_id, "view_activity"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        try:
            page = int(data.split("_")[2])
        except Exception:
            page = 1
        text, kb = build_activity_page_text_and_keyboard(page=page)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # ── PANEL: Ask Me Questions ───────────────────────────────────────────────
    elif data == "adm_ask_me":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        log_activity(query.from_user, "view_ask_me")
        questions = get_all_pending_questions()

        lines = ["❓ *أسئلة الطلاب*\n━━━━━━━━━━━━━━━━━━━\n"]

        if not questions:
            lines.append("لا توجد أسئلة قيد الانتظار.")
        else:
            for q in questions:
                user = q.get("users") or {}
                username = (
                    f"@{user.get('username')}"
                    if user.get("username")
                    else user.get("first_name") or "مجهول"
                )
                user_id_q = user.get("id", "?")
                question_text = (
                    q["question"][:40] + "..."
                    if len(q["question"]) > 40
                    else q["question"]
                )
                lines.append(f"• {username} (ID:{user_id_q})")
                lines.append(f"  _{question_text}_")
                lines.append(f"  [/answer {q['id']}]")
                lines.append("")

        lines.append("\nللرد: أرسل `/answer <رقم السؤال> <الإجابة>`")

        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    # ── PANEL: File Requests ─────────────────────────────────────────────────
    elif data == "adm_file_requests":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        log_activity(query.from_user, "view_file_requests")
        try:
            requests = get_all_pending_file_requests()
        except Exception as e:
            logger.error(f"Error fetching file requests: {e}")
            await query.edit_message_text(
                "⚠️ جدول طلبات الملفات غير موجود.\nيرجى إنشائه في Supabase.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
                ),
            )
            return

        lines = ["📄 *طلبات الملفات*\n━━━━━━━━━━━━━━━━━━━\n"]

        if not requests:
            lines.append("لا توجد طلبات قيد الانتظار.")
        else:
            for req in requests:
                user = req.get("users") or {}
                username = (
                    f"@{user.get('username')}"
                    if user.get("username")
                    else user.get("first_name") or "مجهول"
                )
                user_id_req = user.get("id", "?")
                lines.append(f"• {username} (ID:{user_id_req})")
                lines.append(f"  📝 {req['request_text']}")
                lines.append(f"  [/fulfill_{req['id']}] [/reject_{req['id']}]")
                lines.append("")

        lines.append(
            "\n💡 للأخذ: `/fulfill_رقم_الطلب`\n❌ للرفض: `/reject_رقم_الطلب <السبب>`"
        )

        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    # ── Handle fulfill/reject file requests ─────────────────────────────────────
    elif data.startswith("fulfill_"):
        if not admin_can(user_id, "upload_files"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        try:
            request_id = int(data.split("_")[1])
            fulfill_file_request(request_id, user_id)
            await query.answer("✅ تم تحديد الطلب كمكتمل!", show_alert=True)
            # Refresh the file requests list
            requests = get_all_pending_file_requests()
        except Exception as e:
            logger.error(f"Error fulfilling request: {e}")
            await query.answer("⚠️ الجدول غير موجود.", show_alert=True)
            return
        lines = ["📄 *طلبات الملفات*\n━━━━━━━━━━━━━━━━━━━\n"]
        if not requests:
            lines.append("لا توجد طلبات قيد الانتظار.")
        else:
            for req in requests:
                user = req.get("users") or {}
                username = (
                    f"@{user.get('username')}"
                    if user.get("username")
                    else user.get("first_name") or "مجهول"
                )
                lines.append(f"• {username}")
                lines.append(f"  📝 {req['request_text']}")
                lines.append(f"  [/fulfill_{req['id']}] [/reject_{req['id']}]")
                lines.append("")
        lines.append(
            "\n💡 للأخذ: `/fulfill_رقم_الطلب`\n❌ للرفض: `/reject_رقم_الطلب <السبب>`"
        )
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    elif data.startswith("reject_"):
        if not admin_can(user_id, "upload_files"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        try:
            request_id = int(data.split("_")[1])
            reject_file_request(request_id, user_id, None)
            await query.answer("❌ تم رفض الطلب!", show_alert=True)
            # Refresh the file requests list
            requests = get_all_pending_file_requests()
        except Exception as e:
            logger.error(f"Error rejecting request: {e}")
            await query.answer("⚠️ الجدول غير موجود.", show_alert=True)
            return
        lines = ["📄 *طلبات الملفات*\n━━━━━━━━━━━━━━━━━━━\n"]
        if not requests:
            lines.append("لا توجد طلبات قيد الانتظار.")
        else:
            for req in requests:
                user = req.get("users") or {}
                username = (
                    f"@{user.get('username')}"
                    if user.get("username")
                    else user.get("first_name") or "مجهول"
                )
                lines.append(f"• {username}")
                lines.append(f"  📝 {req['request_text']}")
                lines.append(f"  [/fulfill_{req['id']}] [/reject_{req['id']}]")
                lines.append("")
        lines.append(
            "\n💡 للأخذ: `/fulfill_رقم_الطلب`\n❌ للرفض: `/reject_رقم_الطلب <السبب>`"
        )
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")]]
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    # ── PANEL: manage subjects ────────────────────────────────────────────────
    elif data == "adm_subjects":
        await query.answer("الأقسام ثابتة ولا يمكن إدارتها من هنا.", show_alert=True)
        return

    # ── PANEL: new subject ────────────────────────────────────────────────────
    elif data == "adm_new_subject":
        await query.answer("الأقسام ثابتة ولا يمكن إضافة قسم جديد.", show_alert=True)
        return

    # ── PANEL: manage admins ──────────────────────────────────────────────────
    elif data == "adm_admins":
        if not admin_can(user_id, "manage_admins"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        admins = get_admins()
        lines = ["👥 *إدارة الأدمنز*\n━━━━━━━━━━━━━━━━━━━\n"]
        if admins:
            for a in admins:
                label = _format_user_label_md(a)
                lines.append(f"• {label} (ID:{a['id']})")
        else:
            lines.append("لا يوجد أدمنز مضافون بعد.")
        lines.append("\n_لإضافة أدمن: أرسل معرفه الرقمي بعد الضغط على زر الإضافة_")
        kb = [
            [InlineKeyboardButton("➕ إضافة أدمن", callback_data="adm_add_admin")],
        ]
        if admins:
            for a in admins:
                name = a["first_name"] or str(a["id"])
                kb.append(
                    [
                        InlineKeyboardButton(
                            f"🗑 حذف {name}", callback_data=f"adm_del_admin_{a['id']}"
                        )
                    ]
                )
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")])
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    elif data == "adm_permissions":
        if not is_owner(user_id):
            await query.answer("⛔ للمالك فقط.", show_alert=True)
            return
        admins = [a for a in get_admins() if a.get("id") != OWNER_ID]
        lines = ["⚙️ *صلاحيات الأدمنز*\nاختر أدمن للتعديل:"]
        kb = []
        if admins:
            for a in admins:
                label = _format_user_label_plain(a)
                kb.append(
                    [
                        InlineKeyboardButton(
                            f"{label} (ID:{a['id']})",
                            callback_data=f"perm_admin_{a['id']}",
                        )
                    ]
                )
        else:
            lines.append("لا يوجد أدمنز لإدارة صلاحياتهم.")
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")])
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    elif data.startswith("perm_admin_"):
        if not is_owner(user_id):
            await query.answer("⛔ للمالك فقط.", show_alert=True)
            return
        admin_id = int(data.split("_")[2])
        admin = get_admin_by_id(admin_id)
        if not admin:
            await query.edit_message_text("⚠️ الأدمن غير موجود.")
            return
        label = _format_user_label_md(admin)
        lines = [f"⚙️ *صلاحيات الأدمن*\n{label} (ID:{admin_id})"]
        kb = []
        for perm, title in PERMISSIONS.items():
            enabled = _perm_enabled(admin, perm)
            icon = "✅" if enabled else "❌"
            kb.append(
                [
                    InlineKeyboardButton(
                        f"{icon} {title}",
                        callback_data=f"toggle_perm_{admin_id}_{perm}",
                    )
                ]
            )
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_permissions")])
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    elif data.startswith("toggle_perm_"):
        if not is_owner(user_id):
            await query.answer("⛔ للمالك فقط.", show_alert=True)
            return
        parts = data.split("_", 2)
        if len(parts) < 3:
            await query.answer("⚠️ طلب غير صالح.", show_alert=True)
            return
        rest = parts[2]
        admin_id_str, perm = rest.split("_", 1)
        admin_id = int(admin_id_str)
        if perm not in PERMISSIONS:
            await query.answer("⚠️ صلاحية غير معروفة.", show_alert=True)
            return
        admin = get_admin_by_id(admin_id)
        if not admin:
            await query.edit_message_text("⚠️ الأدمن غير موجود.")
            return
        new_val = not _perm_enabled(admin, perm)
        supabase.table("admins").update({perm: new_val}).eq("id", admin_id).execute()
        _invalidate_admins_cache()
        admin = get_admin_by_id(admin_id)
        label = _format_user_label_md(admin)
        lines = [f"⚙️ *صلاحيات الأدمن*\n{label} (ID:{admin_id})"]
        kb = []
        for p, title in PERMISSIONS.items():
            enabled = _perm_enabled(admin, p)
            icon = "✅" if enabled else "❌"
            kb.append(
                [
                    InlineKeyboardButton(
                        f"{icon} {title}", callback_data=f"toggle_perm_{admin_id}_{p}"
                    )
                ]
            )
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_permissions")])
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    elif data == "adm_add_admin":
        if not admin_can(user_id, "manage_admins"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        await query.edit_message_text(
            "👤 *إضافة أدمن جديد*\n\n"
            "أرسل المعرف الرقمي للشخص (ID).\n"
            "يمكنه معرفة ID عن طريق @userinfobot",
            parse_mode="Markdown",
        )
        context.user_data["awaiting_admin_id"] = True

    elif data.startswith("adm_del_admin_"):
        if not admin_can(user_id, "manage_admins"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        admin_id = int(data.split("_")[3])
        remove_admin(admin_id)
        await query.answer("✅ تم حذف الأدمن.", show_alert=True)
        # Refresh admins list
        admins = get_admins()
        lines = ["👥 *إدارة الأدمنز*\n━━━━━━━━━━━━━━━━━━━\n"]
        if admins:
            for a in admins:
                label = _format_user_label_md(a)
                lines.append(f"• {label} (ID:{a['id']})")
        else:
            lines.append("لا يوجد أدمنز بعد.")
        kb = [[InlineKeyboardButton("➕ إضافة أدمن", callback_data="adm_add_admin")]]
        for a in admins:
            name = a["first_name"] or str(a["id"])
            kb.append(
                [
                    InlineKeyboardButton(
                        f"🗑 حذف {name}", callback_data=f"adm_del_admin_{a['id']}"
                    )
                ]
            )
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_back")])
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )

    # ── PANEL: broadcast ──────────────────────────────────────────────────────
    elif data == "adm_broadcast":
        if not admin_can(user_id, "broadcast"):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        log_activity(query.from_user, "broadcast_prompt")
        users = get_all_users()
        await query.edit_message_text(
            f"📢 *إرسال إذاعة*\n\n"
            f"👥 المستخدمون: *{len(users)}*\n\n"
            "✍️ أرسل رسالتك الآن (نص أو أي ملف) وسيتم إدرجها في قائمة الإذاعة:",
            parse_mode="Markdown",
        )
        context.user_data["awaiting_broadcast_message"] = True

    # ── PANEL: archive ────────────────────────────────────────────────────────
    elif data == "adm_archive":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        await send_archive(query, edit=True)

    # ── PANEL: back ───────────────────────────────────────────────────────────
    elif data == "adm_back":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح.", show_alert=True)
            return
        await send_panel(query, query.from_user.id, edit=True)


def main():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(60.0)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", panel_command))
    application.add_handler(CommandHandler("admin", panel_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("commands", commands_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("ai", ai_engineer_command))
    application.add_handler(CommandHandler("echo", echo_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mysubs", mysubs_command))
    application.add_handler(CommandHandler("unread", unread_command))
    application.add_handler(CommandHandler("favorites", favorites_command))
    application.add_handler(CommandHandler("mystats", mystats_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("archive", archive_command))
    application.add_handler(CommandHandler("answer", answer_command))
    application.add_handler(CommandHandler("request", request_command))
    application.add_handler(CommandHandler("myrequests", myrequests_command))
    application.add_handler(CommandHandler("fulfill", fulfill_request_command))
    application.add_handler(CommandHandler("reject", reject_request_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(FILE_FILTER, handle_file))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    async def error_handler(update, context):
        err = context.error
        if isinstance(err, Conflict):
            logger.warning("getUpdates conflict: another bot instance is running.")
            return
        if isinstance(err, BadRequest) and "Can't parse entities" in str(err):
            logger.warning("BadRequest (parse entities) ignored.")
            return
        logger.exception("Unhandled error", exc_info=err)

    application.add_error_handler(error_handler)

    if not USE_WEBHOOK:
        if RUN_LOCAL_WEB_SERVER:
            from flask import (
                Flask,
                request,
                abort,
                render_template,
                session,
                redirect,
                jsonify,
            )
            from functools import wraps
            from datetime import datetime

            flask_app = Flask(__name__)
            flask_app.secret_key = os.environ.get(
                "SECRET_KEY", "your-secret-key-change-in-production"
            )
            port = int(os.environ.get("PORT", "8000"))

            # Admin IDs for dashboard
            DASHBOARD_ADMIN_IDS = [OWNER_ID]
            try:
                admin_list = supabase.table("admins").select("id").execute()
                for a in admin_list.data or []:
                    DASHBOARD_ADMIN_IDS.append(a["id"])
            except:
                pass

            def dashboard_login_required(f):
                @wraps(f)
                def decorated_function(*args, **kwargs):
                    user_id = session.get("user_id")
                    if not user_id or user_id not in DASHBOARD_ADMIN_IDS:
                        return redirect("/login")
                    return f(*args, **kwargs)

                return decorated_function

            @flask_app.get("/")
            def healthcheck():
                if session.get("user_id") in DASHBOARD_ADMIN_IDS:
                    return redirect("/dashboard")
                return redirect("/login")

            @flask_app.route("/login")
            def dashboard_login():
                return render_template("login.html")

            @flask_app.route("/login", methods=["POST"])
            def dashboard_do_login():
                user_id = request.form.get("user_id", type=int)
                if user_id in DASHBOARD_ADMIN_IDS:
                    session["user_id"] = user_id
                    return redirect("/dashboard")
                return render_template("login.html", error="غير مصرح بالوصول")

            @flask_app.route("/logout")
            def dashboard_logout():
                session.clear()
                return redirect("/login")

            @flask_app.errorhandler(404)
            def dashboard_not_found(e):
                return render_template("404.html"), 404

            @flask_app.route("/files")
            @dashboard_login_required
            def dashboard_files():
                try:
                    files = (
                        supabase.table("files")
                        .select("*")
                        .order("created_at", desc=True)
                        .execute()
                    )
                    return render_template("files.html", files=files.data or [])
                except Exception as e:
                    return render_template("files.html", files=[], error=str(e))

            @flask_app.route("/categories")
            @dashboard_login_required
            def dashboard_categories():
                try:
                    categories = (
                        supabase.table("categories")
                        .select("*")
                        .order("sort_order")
                        .execute()
                    )
                    return render_template(
                        "categories.html", categories=categories.data or []
                    )
                except Exception as e:
                    return render_template(
                        "categories.html", categories=[], error=str(e)
                    )

            @flask_app.route("/activity")
            @dashboard_login_required
            def dashboard_activity():
                try:
                    activities = (
                        supabase.table("user_activity")
                        .select("*")
                        .order("created_at", desc=True)
                        .limit(50)
                        .execute()
                    )
                    return render_template(
                        "activity.html", activities=activities.data or []
                    )
                except Exception as e:
                    return render_template("activity.html", activities=[], error=str(e))

            @flask_app.route("/links/create", methods=["POST"])
            @dashboard_login_required
            def dashboard_create_link():
                try:
                    name = request.form.get("name")
                    url = request.form.get("url")
                    icon = request.form.get("icon", "🔗")
                    description = request.form.get("description", "")
                    sort_order = request.form.get("sort_order", 0, type=int)
                    if not name or not url:
                        return redirect("/links")
                    supabase.table("service_links").insert(
                        {
                            "name": name,
                            "url": url,
                            "icon": icon,
                            "description": description,
                            "sort_order": sort_order,
                        }
                    ).execute()
                    return redirect("/links")
                except:
                    return redirect("/links")

            @flask_app.route("/links/delete/<int:link_id>")
            @dashboard_login_required
            def dashboard_delete_link(link_id):
                try:
                    supabase.table("service_links").delete().eq("id", link_id).execute()
                except:
                    pass
                return redirect("/links")

            @flask_app.route("/links/toggle/<int:link_id>")
            @dashboard_login_required
            def dashboard_toggle_link(link_id):
                try:
                    resp = (
                        supabase.table("service_links")
                        .select("is_active")
                        .eq("id", link_id)
                        .limit(1)
                        .execute()
                    )
                    if resp.data:
                        current = resp.data[0].get("is_active", True)
                        supabase.table("service_links").update(
                            {"is_active": not current}
                        ).eq("id", link_id).execute()
                except:
                    pass
                return redirect("/links")

            @flask_app.route("/settings/maintenance", methods=["POST"])
            @dashboard_login_required
            def dashboard_maintenance():
                try:
                    enabled = request.form.get("enabled") == "true"
                    supabase.table("bot_settings").upsert(
                        {
                            "setting_key": "maintenance_mode",
                            "setting_value": str(enabled),
                            "updated_at": datetime.now().isoformat(),
                        }
                    ).execute()
                    return redirect("/settings")
                except:
                    return redirect("/settings")

            @flask_app.route("/settings/update", methods=["POST"])
            @dashboard_login_required
            def dashboard_update_settings():
                try:
                    setting_key = request.form.get("setting_key")
                    setting_value = request.form.get("setting_value")
                    if setting_key:
                        supabase.table("bot_settings").upsert(
                            {
                                "setting_key": setting_key,
                                "setting_value": setting_value,
                                "updated_at": datetime.now().isoformat(),
                            }
                        ).eq("setting_key", setting_key).execute()
                    return redirect("/settings")
                except:
                    return redirect("/settings")

            @flask_app.route("/broadcasts")
            @dashboard_login_required
            def dashboard_broadcasts():
                try:
                    broadcasts = (
                        supabase.table("broadcasts")
                        .select("*")
                        .order("created_at", desc=True)
                        .execute()
                    )
                    return render_template(
                        "broadcasts.html", broadcasts=broadcasts.data or []
                    )
                except Exception as e:
                    return render_template(
                        "broadcasts.html", broadcasts=[], error=str(e)
                    )

            @flask_app.route("/broadcasts/create", methods=["GET", "POST"])
            @dashboard_login_required
            def dashboard_create_broadcast():
                if request.method == "POST":
                    try:
                        message = request.form.get("message")
                        if message:
                            all_users = supabase.table("users").select("id").execute()
                            total_users = len(all_users.data) if all_users.data else 0
                            supabase.table("broadcasts").insert(
                                {
                                    "created_by": session.get("user_id"),
                                    "status": "pending",
                                    "payload": {"kind": "text", "text": message},
                                    "total_users": total_users,
                                }
                            ).execute()
                            return redirect("/broadcasts")
                    except:
                        return redirect("/broadcasts/create")
                return render_template("create_broadcast.html")

            @flask_app.route("/dashboard")
            @dashboard_login_required
            def dashboard():
                try:
                    users = (
                        supabase.table("users").select("id", count="exact").execute()
                    )
                    files = (
                        supabase.table("files").select("id", count="exact").execute()
                    )
                    subjects = (
                        supabase.table("subjects").select("id", count="exact").execute()
                    )
                    broadcasts = (
                        supabase.table("broadcasts")
                        .select("id", count="exact")
                        .execute()
                    )
                    questions = (
                        supabase.table("ask_me_questions")
                        .select("id", count="exact")
                        .execute()
                    )

                    stats = {
                        "users": users.count or 0,
                        "files": files.count or 0,
                        "subjects": subjects.count or 0,
                        "broadcasts": broadcasts.count or 0,
                        "questions": questions.count or 0,
                    }
                    return render_template("dashboard.html", stats=stats)
                except Exception as e:
                    return render_template("dashboard.html", stats={}, error=str(e))

            @flask_app.route("/api/stats")
            @dashboard_login_required
            def api_stats():
                try:
                    users = (
                        supabase.table("users").select("id", count="exact").execute()
                    )
                    files = (
                        supabase.table("files").select("id", count="exact").execute()
                    )
                    subjects = (
                        supabase.table("subjects").select("id", count="exact").execute()
                    )
                    return jsonify(
                        {
                            "users": users.count or 0,
                            "files": files.count or 0,
                            "subjects": subjects.count or 0,
                        }
                    )
                except Exception as e:
                    return jsonify({"error": str(e)}), 500

            @flask_app.route("/settings")
            @dashboard_login_required
            def dashboard_settings():
                try:
                    settings_list = supabase.table("bot_settings").select("*").execute()
                    maintenance_enabled = False
                    if settings_list.data:
                        for s in settings_list.data:
                            if (
                                s.get("setting_key") == "maintenance_mode"
                                and s.get("setting_value") == "True"
                            ):
                                maintenance_enabled = True
                    return render_template(
                        "settings.html",
                        settings=settings_list.data or [],
                        maintenance_enabled=maintenance_enabled,
                    )
                except Exception as e:
                    return render_template(
                        "settings.html",
                        settings=[],
                        maintenance_enabled=False,
                        error=str(e),
                    )

            @flask_app.route("/links")
            @dashboard_login_required
            def dashboard_links():
                try:
                    links_list = (
                        supabase.table("service_links")
                        .select("*")
                        .order("sort_order")
                        .execute()
                    )
                    return render_template("links.html", links=links_list.data or [])
                except Exception as e:
                    return render_template("links.html", links=[], error=str(e))

            threading.Thread(
                target=lambda: flask_app.run(host="0.0.0.0", port=port, debug=False),
                daemon=True,
            ).start()
            logger.info("Web Dashboard started on http://0.0.0.0:%s", port)

        # Ensure an event loop exists in main thread for PTB polling (Py3.11+)
        if sys.platform.startswith("win"):
            try:
                policy = asyncio.WindowsSelectorEventLoopPolicy()
                asyncio.set_event_loop_policy(policy)
            except Exception:
                pass
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ensure_broadcast_worker(loop, application)

        # Ensure no webhook is set to avoid getUpdates conflict
        try:
            loop.run_until_complete(
                application.bot.delete_webhook(drop_pending_updates=True)
            )
        except Exception as e:
            logger.warning(f"Failed to delete webhook (this is usually ok): {e}")

        logger.info("Bot is running (polling mode)...")
        while True:
            try:
                application.run_polling(
                    drop_pending_updates=True,
                    close_loop=False,
                    timeout=30,  # Add timeout to prevent hanging
                    read_timeout=30,
                    write_timeout=30,
                )
                break
            except Conflict:
                logger.warning("Polling conflict detected. Retrying in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                logger.exception(f"Polling crashed: {e}. Retrying in 5 seconds...")
                time.sleep(5)
        return

    from flask import Flask, request, abort, render_template, session, redirect, jsonify
    from functools import wraps
    from datetime import datetime

    flask_app = Flask(__name__)
    flask_app.secret_key = os.environ.get(
        "SECRET_KEY", "your-secret-key-change-in-production"
    )

    webhook_path = os.environ.get("WEBHOOK_PATH", "/webhook")
    webhook_url = os.environ.get("WEBHOOK_URL")
    webhook_secret = os.environ.get("WEBHOOK_SECRET_TOKEN")
    port = int(os.environ.get("PORT", "8080"))

    # Admin IDs for dashboard
    DASHBOARD_ADMIN_IDS = [OWNER_ID]
    try:
        admin_list = supabase.table("admins").select("id").execute()
        for a in admin_list.data or []:
            DASHBOARD_ADMIN_IDS.append(a["id"])
    except:
        pass

    def dashboard_login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id or user_id not in DASHBOARD_ADMIN_IDS:
                return redirect("/login")
            return f(*args, **kwargs)

        return decorated_function

    @flask_app.get("/")
    def healthcheck():
        if session.get("user_id") in DASHBOARD_ADMIN_IDS:
            return redirect("/dashboard")
        return redirect("/login")

    @flask_app.route("/login")
    def dashboard_login():
        return render_template("login.html")

    @flask_app.route("/login", methods=["POST"])
    def dashboard_do_login():
        user_id = request.form.get("user_id", type=int)
        if user_id in DASHBOARD_ADMIN_IDS:
            session["user_id"] = user_id
            return redirect("/dashboard")
        return render_template("login.html", error="غير مصرح بالوصول")

    @flask_app.route("/logout")
    def dashboard_logout():
        session.clear()
        return redirect("/login")

    @flask_app.route("/dashboard")
    @dashboard_login_required
    def dashboard():
        try:
            users = supabase.table("users").select("id", count="exact").execute()
            files = supabase.table("files").select("id", count="exact").execute()
            subjects = supabase.table("subjects").select("id", count="exact").execute()
            broadcasts = (
                supabase.table("broadcasts").select("id", count="exact").execute()
            )
            questions = (
                supabase.table("ask_me_questions").select("id", count="exact").execute()
            )

            stats = {
                "users": users.count or 0,
                "files": files.count or 0,
                "subjects": subjects.count or 0,
                "broadcasts": broadcasts.count or 0,
                "questions": questions.count or 0,
            }
            return render_template("dashboard.html", stats=stats)
        except Exception as e:
            return render_template("dashboard.html", stats={}, error=str(e))

    @flask_app.route("/api/stats")
    @dashboard_login_required
    def api_stats():
        try:
            users = supabase.table("users").select("id", count="exact").execute()
            files = supabase.table("files").select("id", count="exact").execute()
            subjects = supabase.table("subjects").select("id", count="exact").execute()
            return jsonify(
                {
                    "users": users.count or 0,
                    "files": files.count or 0,
                    "subjects": subjects.count or 0,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @flask_app.route("/users")
    @dashboard_login_required
    def dashboard_users():
        try:
            page = request.args.get("page", 1, type=int)
            per_page = 20
            offset = (page - 1) * per_page
            users = (
                supabase.table("users")
                .select("*")
                .order("id")
                .range(offset, offset + per_page - 1)
                .execute()
            )
            total = supabase.table("users").select("id", count="exact").execute()
            return render_template(
                "users.html",
                users=users.data or [],
                page=page,
                total_pages=(total.count or 0) // per_page + 1,
            )
        except Exception as e:
            return render_template("users.html", users=[], error=str(e))

    @flask_app.route("/broadcasts")
    @dashboard_login_required
    def dashboard_broadcasts():
        try:
            page = request.args.get("page", 1, type=int)
            per_page = 20
            offset = (page - 1) * per_page
            broadcasts_list = (
                supabase.table("broadcasts")
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + per_page - 1)
                .execute()
            )
            total = supabase.table("broadcasts").select("id", count="exact").execute()
            return render_template(
                "broadcasts.html",
                broadcasts=broadcasts_list.data or [],
                page=page,
                total_pages=(total.count or 0) // per_page + 1,
            )
        except Exception as e:
            return render_template("broadcasts.html", broadcasts=[], error=str(e))

    @flask_app.route("/broadcasts/create", methods=["GET", "POST"])
    @dashboard_login_required
    def dashboard_create_broadcast():
        if request.method == "GET":
            return render_template("create_broadcast.html")
        try:
            message = request.form.get("message", "")
            if not message:
                return render_template("create_broadcast.html", error="الرسالة مطلوبة")
            payload = {"kind": "text", "text": message, "parse_mode": "Markdown"}
            supabase.table("broadcasts").insert(
                {
                    "created_by": session.get("user_id"),
                    "status": "pending",
                    "payload": payload,
                }
            ).execute()
            return redirect("/broadcasts")
        except Exception as e:
            return render_template("create_broadcast.html", error=str(e))

    @flask_app.route("/settings")
    @dashboard_login_required
    def dashboard_settings():
        try:
            settings_list = supabase.table("bot_settings").select("*").execute()
            maintenance_enabled = False
            if settings_list.data:
                for s in settings_list.data:
                    if (
                        s.get("setting_key") == "maintenance_mode"
                        and s.get("setting_value") == "True"
                    ):
                        maintenance_enabled = True
            return render_template(
                "settings.html",
                settings=settings_list.data or [],
                maintenance_enabled=maintenance_enabled,
            )
        except Exception as e:
            return render_template(
                "settings.html", settings=[], maintenance_enabled=False, error=str(e)
            )

    @flask_app.route("/links")
    @dashboard_login_required
    def dashboard_links():
        try:
            links_list = (
                supabase.table("service_links")
                .select("*")
                .order("sort_order")
                .execute()
            )
            return render_template("links.html", links=links_list.data or [])
        except Exception as e:
            return render_template("links.html", links=[], error=str(e))

    @flask_app.errorhandler(404)
    def dashboard_not_found(e):
        return render_template("404.html"), 404

    @flask_app.route("/files")
    @dashboard_login_required
    def dashboard_files():
        try:
            files = (
                supabase.table("files")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return render_template("files.html", files=files.data or [])
        except Exception as e:
            return render_template("files.html", files=[], error=str(e))

    @flask_app.route("/categories")
    @dashboard_login_required
    def dashboard_categories():
        try:
            categories = (
                supabase.table("categories").select("*").order("sort_order").execute()
            )
            return render_template("categories.html", categories=categories.data or [])
        except Exception as e:
            return render_template("categories.html", categories=[], error=str(e))

    @flask_app.route("/activity")
    @dashboard_login_required
    def dashboard_activity():
        try:
            activities = (
                supabase.table("user_activity")
                .select("*")
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            return render_template("activity.html", activities=activities.data or [])
        except Exception as e:
            return render_template("activity.html", activities=[], error=str(e))

    @flask_app.route("/links/create", methods=["POST"])
    @dashboard_login_required
    def dashboard_create_link():
        try:
            name = request.form.get("name")
            url = request.form.get("url")
            icon = request.form.get("icon", "🔗")
            description = request.form.get("description", "")
            sort_order = request.form.get("sort_order", 0, type=int)
            if not name or not url:
                return redirect("/links")
            supabase.table("service_links").insert(
                {
                    "name": name,
                    "url": url,
                    "icon": icon,
                    "description": description,
                    "sort_order": sort_order,
                }
            ).execute()
            return redirect("/links")
        except:
            return redirect("/links")

    @flask_app.route("/links/delete/<int:link_id>")
    @dashboard_login_required
    def dashboard_delete_link(link_id):
        try:
            supabase.table("service_links").delete().eq("id", link_id).execute()
        except:
            pass
        return redirect("/links")

    @flask_app.route("/links/toggle/<int:link_id>")
    @dashboard_login_required
    def dashboard_toggle_link(link_id):
        try:
            resp = (
                supabase.table("service_links")
                .select("is_active")
                .eq("id", link_id)
                .limit(1)
                .execute()
            )
            if resp.data:
                current = resp.data[0].get("is_active", True)
                supabase.table("service_links").update({"is_active": not current}).eq(
                    "id", link_id
                ).execute()
        except:
            pass
        return redirect("/links")

    @flask_app.route("/settings/maintenance", methods=["POST"])
    @dashboard_login_required
    def dashboard_maintenance():
        try:
            enabled = request.form.get("enabled") == "true"
            supabase.table("bot_settings").upsert(
                {
                    "setting_key": "maintenance_mode",
                    "setting_value": str(enabled),
                    "updated_at": datetime.now().isoformat(),
                }
            ).execute()
            return redirect("/settings")
        except:
            return redirect("/settings")

    @flask_app.route("/settings/update", methods=["POST"])
    @dashboard_login_required
    def dashboard_update_settings():
        try:
            setting_key = request.form.get("setting_key")
            setting_value = request.form.get("setting_value")
            if setting_key:
                supabase.table("bot_settings").upsert(
                    {
                        "setting_key": setting_key,
                        "setting_value": setting_value,
                        "updated_at": datetime.now().isoformat(),
                    }
                ).eq("setting_key", setting_key).execute()
            return redirect("/settings")
        except:
            return redirect("/settings")

    @flask_app.post(webhook_path)
    def telegram_webhook():
        if webhook_secret:
            header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header != webhook_secret:
                abort(403)
        data = request.get_json(force=True, silent=True)
        if not data:
            return "bad request", 400
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return "ok"

    # Set up event loop for webhook mode
    loop = asyncio.new_event_loop()

    def _run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    threading.Thread(target=_run_loop, daemon=True).start()
    ensure_broadcast_worker(loop, application)

    async def _init_bot():
        await application.initialize()
        await application.start()
        if webhook_url:
            await application.bot.set_webhook(
                url=webhook_url.rstrip("/") + webhook_path,
                secret_token=webhook_secret,
                drop_pending_updates=True,
            )

    asyncio.run_coroutine_threadsafe(_init_bot(), loop)

    logger.info("Bot is running (webhook + Flask + Dashboard mode)...")
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
