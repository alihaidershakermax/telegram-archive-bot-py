import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Get API settings from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")

# Determine which provider to use
AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq").lower()  # "openai" or "groq"

# Initialize client
_client = None


def get_ai_client():
    """Get the AI client based on provider setting"""
    global _client

    if _client is not None:
        return _client

    if AI_PROVIDER == "groq":
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not configured")
            return None
        try:
            from groq import AsyncGroq

            _client = AsyncGroq(api_key=GROQ_API_KEY)
            _client._provider = "groq"
            return _client
        except ImportError:
            logger.warning("groq package not installed, falling back to OpenAI")

    # Default to OpenAI
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not configured")
        return None

    try:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        _client._provider = "openai"
        return _client
    except ImportError:
        logger.error("Neither groq nor openai package available")
        return None


def get_sync_ai_client():
    """Get synchronous AI client"""
    global _sync_client
    if not hasattr(get_sync_ai_client, "_sync_client"):
        get_sync_ai_client._sync_client = None

    if get_sync_ai_client._sync_client is not None:
        return get_sync_ai_client._sync_client

    if AI_PROVIDER == "groq":
        if not GROQ_API_KEY:
            return None
        try:
            from groq import Groq

            get_sync_ai_client._sync_client = Groq(api_key=GROQ_API_KEY)
            get_sync_ai_client._sync_client._provider = "groq"
            return get_sync_ai_client._sync_client
        except ImportError:
            pass

    if not OPENAI_API_KEY:
        return None

    try:
        from openai import OpenAI

        get_sync_ai_client._sync_client = OpenAI(api_key=OPENAI_API_KEY)
        get_sync_ai_client._sync_client._provider = "openai"
        return get_sync_ai_client._sync_client
    except ImportError:
        return None


# ============================================================
# Petroleum Engineering System Prompt
# ============================================================

PETROLEUM_SYSTEM_PROMPT = """أنت مساعد متخصص في هندسة النفط والغاز. اكتب إجابات مختصرة ومفيدة.

## القواعد:
- اجب بشكل مختصر (3-5 أسطر maximum)
- لا تستخدم رموز تنسيق مثل *, #, _
- استخدم المصطلحات الإنجليزية عند الحاجة
- لا ترد على أسئلة خارج مجال النفط والغاز
- كن مباشراً في الإجابة"""

PETROLEUM_QUICK_PROMPT = (
    """أجب بشكل مختصر ومفيد عن سؤال مهندس نفط. ركز على النقاط الأساسية."""
)

PETROLEUM_DETAILED_PROMPT = (
    """أجب بشكل شامل ومفصل عن سؤال مهندس نفط. اشرح المفاهيم بعمق."""
)


def build_prompt(user_message: str, mode: str = "quick") -> str:
    """Build prompt based on mode"""
    if mode == "detailed":
        return f"{PETROLEUM_DETAILED_PROMPT}\n\nالسؤال: {user_message}"
    return f"{PETROLEUM_QUICK_PROMPT}\n\nالسؤال: {user_message}"


async def ask_ai(user_message: str, mode: str = "quick") -> str:
    """Send question to AI and get response"""
    client = get_ai_client()
    if not client:
        return "⚠️ خدمة الذكاء الاصطناعي غير متاحة حالياً.\nيرجى التواصل مع الإدارة لتفعيل الخدمة."

    provider = getattr(client, "_provider", "openai")
    model = GROQ_MODEL if provider == "groq" else OPENAI_MODEL

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PETROLEUM_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=256,
            temperature=0.5,
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"AI request failed: {e}")
        return f"⚠️ حدث خطأ في معالجة طلبك.\nالخطأ: {str(e)}"


async def ask_ai_with_context(
    user_message: str, context: Dict[str, Any], mode: str = "quick"
) -> str:
    """Ask AI with additional context like subject name, file info"""
    client = get_ai_client()
    if not client:
        return "⚠️ خدمة الذكاء الاصطناعي غير متاحة حالياً."

    provider = getattr(client, "_provider", "openai")
    model = GROQ_MODEL if provider == "groq" else OPENAI_MODEL

    # Build context-aware prompt
    context_info = ""
    if context.get("subject_name"):
        context_info += f"\n📚 المادة: {context['subject_name']}"
    if context.get("file_name"):
        context_info += f"\n📄 الملف: {context['file_name']}"
    if context.get("category"):
        context_info += f"\n📁 القسم: {context['category']}"

    full_message = (
        f"{context_info}\n\n❓ السؤال: {user_message}" if context_info else user_message
    )

    try:
        provider = getattr(client, "_provider", "openai")
        model = GROQ_MODEL if provider == "groq" else OPENAI_MODEL

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PETROLEUM_SYSTEM_PROMPT},
                {"role": "user", "content": full_message},
            ],
            max_tokens=256,
            temperature=0.5,
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"AI request with context failed: {e}")
        return f"⚠️ حدث خطأ في معالجة طلبك.\nالخطأ: {str(e)}"


# ============================================================
# Quick Topics for Petroleum Engineers
# ============================================================

PETROLEUM_TOPICS = {
    "production": {
        "ar": "هندسة الإنتاج",
        "questions": [
            "ما هي أفضل طرق زيادة إنتاجية البئر؟",
            "كيف أحلل منحنى الإنتاج؟",
            "ما هي مشاكل الإنتاج الشائعة وكيفية حلها؟",
        ],
    },
    "reservoir": {
        "ar": "هندسة الخزانات",
        "questions": [
            "كيف أحسب الاحتياطيات؟",
            "ما هي نظريات التدفق في الخزان؟",
            "كيف أخطط لاستعادة النفط؟",
        ],
    },
    "drilling": {
        "ar": "هندسة الحفر",
        "questions": [
            "ما هي أنواع الآبار؟",
            "كيف أصمم برنامج الحفر؟",
            "ما هي مشاكل الحفر الشائعة؟",
        ],
    },
    "processing": {
        "ar": "معالجة النفط",
        "questions": [
            "كيف أفصل الغاز عن النفط؟",
            "ما هي مراحل معالجة النفط الخام؟",
            "كيف أتعامل مع الماء والملح؟",
        ],
    },
    "safety": {
        "ar": "السلامة",
        "questions": [
            "ما معايير السلامة في الصناعة؟",
            "كيف أخطط للطوارئ؟",
            "ما معدات الحماية المطلوبة؟",
        ],
    },
}


def get_topic_keyboard():
    """Get inline keyboard for quick topics"""
    from telegram import InlineKeyboardButton

    keyboard = []
    for key, topic in PETROLEUM_TOPICS.items():
        keyboard.append(
            [InlineKeyboardButton(f"🏭 {topic['ar']}", callback_data=f"ai_topic_{key}")]
        )
    keyboard.append(
        [InlineKeyboardButton("❓ سؤال حر", callback_data="ai_free_question")]
    )
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_start")])
    return keyboard


def get_topic_questions(topic_key: str) -> list:
    """Get predefined questions for a topic"""
    topic = PETROLEUM_TOPICS.get(topic_key)
    if topic:
        return topic.get("questions", [])
    return []


# ============================================================
# AI Stats and Usage
# ============================================================

_ai_usage_cache = {"data": None, "ts": 0.0}


def get_ai_usage():
    """Get AI usage stats"""
    from supabase_client import supabase
    import time

    cache = _ai_usage_cache
    if cache["data"] is not None and (time.time() - cache["ts"]) < 60:
        return cache["data"]

    try:
        resp = supabase.table("ai_chats").select("id", count="exact").execute()
        count = resp.count if resp.count is not None else len(resp.data or [])

        resp_users = (
            supabase.table("ai_chats").select("user_id", count="exact").execute()
        )
        unique_users = (
            resp_users.count
            if hasattr(resp_users, "count") and resp_users.count is not None
            else len(
                set(
                    r.get("user_id")
                    for r in (resp_users.data or [])
                    if r.get("user_id")
                )
            )
        )

        cache["data"] = {"total_chats": count, "unique_users": unique_users}
        cache["ts"] = time.time()
        return cache["data"]
    except Exception as e:
        logger.error(f"Failed to get AI stats: {e}")
        return {"total_chats": 0, "unique_users": 0}


def log_ai_chat(user_id: int, message: str, response: str):
    """Log AI conversation"""
    from supabase_client import supabase

    try:
        supabase.table("ai_chats").insert(
            {"user_id": user_id, "message": message, "response": response}
        ).execute()
    except Exception as e:
        logger.error(f"Failed to log AI chat: {e}")
