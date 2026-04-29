import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


# Initialize Supabase client with explicit validation to avoid silent misconfig.
def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )

    if not url or not key:
        raise RuntimeError(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY in environment."
        )

    if key.startswith("sb_publishable_"):
        raise RuntimeError(
            "Invalid Supabase key type. Use anon or service_role key from Project Settings > API."
        )

    return create_client(url, key)


supabase: Client = get_supabase_client()


def ban_user(user_id):
    """Ban a user from using the bot."""
    resp = (
        supabase.table("users").update({"is_banned": True}).eq("id", user_id).execute()
    )
    return True


def unban_user(user_id):
    """Unban a user."""
    resp = (
        supabase.table("users").update({"is_banned": False}).eq("id", user_id).execute()
    )
    return True


def is_user_banned(user_id):
    """Check if a user is banned. Handles missing column gracefully."""
    try:
        resp = (
            supabase.table("users")
            .select("is_banned")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        data = resp.data or []
        if data:
            return data[0].get("is_banned", False)
    except Exception as e:
        # If column doesn't exist, assume not banned to prevent bot crash
        if "is_banned" in str(e):
            return False
        logger.error(f"Error checking ban status: {e}")
    return False


# ─── New Features Helper Functions ───────────────────────────────────────────


def get_user_question_limit(user_id):
    """Get user's question limit info."""
    resp = (
        supabase.table("user_question_limits")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    if data:
        return data[0]
    return {"user_id": user_id, "questions_asked": 0, "max_questions": 3}


def can_user_ask_question(user_id):
    """Check if user can ask more questions."""
    limit_info = get_user_question_limit(user_id)
    return limit_info["questions_asked"] < limit_info["max_questions"]


def get_remaining_questions(user_id):
    """Get remaining questions for user."""
    limit_info = get_user_question_limit(user_id)
    return max(0, limit_info["max_questions"] - limit_info["questions_asked"])


def create_ask_me_question(user_id, question_text):
    """Create a new Ask Me question."""
    resp = (
        supabase.table("ask_me_questions")
        .insert({"user_id": user_id, "question": question_text, "status": "pending"})
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_user_pending_questions(user_id):
    """Get user's pending questions."""
    resp = (
        supabase.table("ask_me_questions")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", ["pending", "answered"])
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_all_pending_questions():
    """Get all pending questions for admins."""
    resp = (
        supabase.table("ask_me_questions")
        .select("*, users(username, first_name)")
        .eq("status", "pending")
        .order("created_at")
        .execute()
    )
    return resp.data or []


def answer_question(question_id, answer_text, admin_id):
    """Answer a question."""
    resp = (
        supabase.table("ask_me_questions")
        .update(
            {
                "answer": answer_text,
                "status": "answered",
                "answered_at": "now()",
                "answered_by": admin_id,
            }
        )
        .eq("id", question_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def close_question(question_id):
    """Close a question."""
    resp = (
        supabase.table("ask_me_questions")
        .update({"status": "closed", "closed_at": "now()"})
        .eq("id", question_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_question_by_id(question_id):
    """Get question by ID with user info."""
    resp = (
        supabase.table("ask_me_questions")
        .select("*, users(username, first_name)")
        .eq("id", question_id)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    return data[0] if data else None


def subscribe_to_subject(user_id, subject_id):
    """Subscribe user to a subject."""
    try:
        resp = (
            supabase.table("subject_subscriptions")
            .insert({"user_id": user_id, "subject_id": subject_id})
            .execute()
        )
        return True
    except Exception:
        return False  # Already subscribed


def unsubscribe_from_subject(user_id, subject_id):
    """Unsubscribe user from a subject."""
    resp = (
        supabase.table("subject_subscriptions")
        .delete()
        .eq("user_id", user_id)
        .eq("subject_id", subject_id)
        .execute()
    )
    return True


def is_subscribed_to_subject(user_id, subject_id):
    """Check if user is subscribed to a subject."""
    resp = (
        supabase.table("subject_subscriptions")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("subject_id", subject_id)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def get_subscribers_for_subject(subject_id):
    """Get all users subscribed to a subject."""
    resp = (
        supabase.table("subject_subscriptions")
        .select("user_id, users(username, first_name)")
        .eq("subject_id", subject_id)
        .execute()
    )
    return resp.data or []


def get_user_subscriptions(user_id):
    """Get all subjects a user is subscribed to."""
    resp = (
        supabase.table("subject_subscriptions")
        .select("*, subjects(name, category_id)")
        .eq("user_id", user_id)
        .execute()
    )
    return resp.data or []


def mark_file_as_viewed(user_id, file_id):
    """Mark a file as viewed by a user."""
    try:
        supabase.table("file_read_tracking").insert(
            {"user_id": user_id, "file_id": file_id}
        ).execute()
    except Exception:
        pass  # Already viewed


def is_file_viewed(user_id, file_id):
    """Check if user has viewed a file."""
    resp = (
        supabase.table("file_read_tracking")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("file_id", file_id)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def get_unread_files_for_user(user_id, subject_id=None):
    """Get unread files for a user, optionally filtered by subject."""
    # Get viewed file IDs for the user
    viewed_resp = (
        supabase.table("file_read_tracking")
        .select("file_id")
        .eq("user_id", user_id)
        .execute()
    )
    viewed_file_ids = [r["file_id"] for r in (viewed_resp.data or [])]

    # Build query for files not viewed by the user
    query = supabase.table("files").select("*, subjects(name)")

    if viewed_file_ids:
        query = query.not_.in_("id", viewed_file_ids)

    if subject_id is not None:
        query = query.eq("subject_id", subject_id)

    query = query.order("created_at", desc=True)

    resp = query.execute()
    return resp.data or []


def add_to_favorites(user_id, file_id):
    """Add a file to user's favorites."""
    try:
        supabase.table("favorites").insert(
            {"user_id": user_id, "file_id": file_id}
        ).execute()
        return True
    except Exception:
        return False  # Already in favorites


def remove_from_favorites(user_id, file_id):
    """Remove a file from user's favorites."""
    resp = (
        supabase.table("favorites")
        .delete()
        .eq("user_id", user_id)
        .eq("file_id", file_id)
        .execute()
    )
    return True


def get_user_favorites(user_id):
    """Get user's favorite files."""
    resp = (
        supabase.table("favorites")
        .select("*, files(name, file_id, file_type, subject_id, subjects(name))")
        .eq("user_id", user_id)
        .execute()
    )
    return resp.data or []


def is_favorite(user_id, file_id):
    """Check if file is in user's favorites."""
    resp = (
        supabase.table("favorites")
        .select("user_id")
        .eq("user_id", user_id)
        .eq("file_id", file_id)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def rate_file(user_id, file_id, rating):
    """Rate a file (1-5)."""
    try:
        supabase.table("file_ratings").upsert(
            {"user_id": user_id, "file_id": file_id, "rating": rating},
            on_conflict="user_id,file_id",
        ).execute()
        return True
    except Exception:
        return False


def get_file_rating(file_id):
    """Get file's average rating and count."""
    resp = (
        supabase.table("file_ratings").select("rating").eq("file_id", file_id).execute()
    )
    ratings = [r["rating"] for r in (resp.data or [])]
    if not ratings:
        return {"avg": 0, "count": 0}
    return {"avg": sum(ratings) / len(ratings), "count": len(ratings)}


def get_user_file_rating(user_id, file_id):
    """Get user's rating for a file."""
    resp = (
        supabase.table("file_ratings")
        .select("rating")
        .eq("user_id", user_id)
        .eq("file_id", file_id)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    return data[0]["rating"] if data else None


def rate_subject(user_id, subject_id, rating):
    """Rate a subject (1-5)."""
    try:
        supabase.table("subject_ratings").upsert(
            {"user_id": user_id, "subject_id": subject_id, "rating": rating},
            on_conflict="user_id,subject_id",
        ).execute()
        return True
    except Exception:
        return False


def get_subject_rating(subject_id):
    """Get subject's average rating and count."""
    resp = (
        supabase.table("subject_ratings")
        .select("rating")
        .eq("subject_id", subject_id)
        .execute()
    )
    ratings = [r["rating"] for r in (resp.data or [])]
    if not ratings:
        return {"avg": 0, "count": 0}
    return {"avg": sum(ratings) / len(ratings), "count": len(ratings)}


def get_user_file_stats(user_id):
    """Get user's file viewing statistics efficiently."""
    resp = (
        supabase.table("file_read_tracking")
        .select("file_id")
        .eq("user_id", user_id)
        .execute()
    )
    viewed_files = resp.data or []
    viewed_count = len(viewed_files)

    if not viewed_files:
        return {"viewed_count": 0, "by_subject": {}}

    # Get all subject_ids for these files in ONE request
    file_ids = [r["file_id"] for r in viewed_files]
    files_resp = (
        supabase.table("files").select("subject_id").in_("id", file_ids).execute()
    )

    # Count by subject
    by_subject = {}
    for f in files_resp.data or []:
        subj_id = f["subject_id"]
        by_subject[subj_id] = by_subject.get(subj_id, 0) + 1

    return {"viewed_count": viewed_count, "by_subject": by_subject}


def get_subject_stats(subject_id):
    """Get statistics for a subject."""
    # Subscriber count
    sub_resp = (
        supabase.table("subject_subscriptions")
        .select("user_id", count="exact")
        .eq("subject_id", subject_id)
        .execute()
    )
    subscriber_count = sub_resp.count or 0

    # File count
    file_resp = (
        supabase.table("files")
        .select("id", count="exact")
        .eq("subject_id", subject_id)
        .execute()
    )
    file_count = file_resp.count or 0

    # Rating
    rating_info = get_subject_rating(subject_id)

    return {
        "subscriber_count": subscriber_count,
        "file_count": file_count,
        "avg_rating": rating_info["avg"],
        "rating_count": rating_info["count"],
    }


# ─── File Requests System ───────────────────────────────────────────────────────


def create_file_request(user_id, request_text):
    """Create a new file request from a user."""
    try:
        resp = (
            supabase.table("file_requests")
            .insert(
                {"user_id": user_id, "request_text": request_text, "status": "pending"}
            )
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.error(f"Error creating file request: {e}")
        return None


def get_user_file_requests(user_id):
    """Get all file requests for a user."""
    resp = (
        supabase.table("file_requests")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_all_pending_file_requests():
    """Get all pending file requests for admins."""
    resp = (
        supabase.table("file_requests")
        .select("*, users(username, first_name)")
        .eq("status", "pending")
        .order("created_at")
        .execute()
    )
    return resp.data or []


def fulfill_file_request(request_id, admin_id):
    """Mark a file request as fulfilled."""
    resp = (
        supabase.table("file_requests")
        .update(
            {"status": "fulfilled", "fulfilled_by": admin_id, "fulfilled_at": "now()"}
        )
        .eq("id", request_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def reject_file_request(request_id, admin_id, reason=None):
    """Reject a file request."""
    resp = (
        supabase.table("file_requests")
        .update(
            {
                "status": "rejected",
                "rejected_by": admin_id,
                "rejected_at": "now()",
                "rejection_reason": reason,
            }
        )
        .eq("id", request_id)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_file_request_by_id(request_id):
    """Get a file request by ID."""
    resp = (
        supabase.table("file_requests")
        .select("*, users(username, first_name)")
        .eq("id", request_id)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    return data[0] if data else None
