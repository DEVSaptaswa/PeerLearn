"""
utils/mongo_client.py
Singleton PyMongo client. All MongoDB operations go through this module.

Collections:
  - discussions : Thread documents (one per channel-thread)
  - messages    : Nested chat messages with soft-delete support
  - search_logs : Query analytics
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pymongo
from bson import ObjectId
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Singleton ──────────────────────────────────────────────────────────────────
_client: pymongo.MongoClient | None = None


def get_client() -> pymongo.MongoClient:
    global _client
    if _client is None:
        _client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
    return _client


def get_db() -> pymongo.database.Database:
    return get_client()[settings.MONGO_DB_NAME]


# ── Collection accessors ───────────────────────────────────────────────────────
def discussions() -> pymongo.collection.Collection:
    return get_db()["discussions"]


def messages() -> pymongo.collection.Collection:
    return get_db()["messages"]


def search_logs() -> pymongo.collection.Collection:
    return get_db()["search_logs"]


# ── Index bootstrap (call once at startup via AppConfig.ready) ─────────────────
def ensure_indexes() -> None:
    try:
        discussions().create_index([("channel_id", pymongo.ASCENDING)])
        discussions().create_index([("title", pymongo.TEXT), ("body", pymongo.TEXT)])
        messages().create_index([("discussion_id", pymongo.ASCENDING)])
        messages().create_index([("author_id", pymongo.ASCENDING)])
        messages().create_index([("body", pymongo.TEXT)])
        search_logs().create_index([("query", pymongo.TEXT)])
        search_logs().create_index([("created_at", pymongo.DESCENDING)])
        logger.info("MongoDB indexes ensured.")
    except Exception as exc:
        logger.warning("Could not create MongoDB indexes: %s", exc)


# ── Discussion helpers ─────────────────────────────────────────────────────────
def create_discussion(
    *,
    channel_id: int,
    author_id: int,
    title: str,
    body: str,
    is_private_channel: bool = False,
) -> str:
    """Insert a new discussion thread. Returns the new ObjectId string."""
    now = datetime.now(timezone.utc)
    doc = {
        "channel_id": channel_id,
        "author_id": author_id,
        "title": title,
        "body": body,
        "is_private_channel": is_private_channel,
        "upvotes": 0,
        "reply_count": 0,
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    result = discussions().insert_one(doc)
    return str(result.inserted_id)


def get_discussion(discussion_id: str) -> dict | None:
    try:
        return discussions().find_one({"_id": ObjectId(discussion_id), "is_deleted": False})
    except Exception:
        return None


def list_discussions(channel_id: int, limit: int = 50, skip: int = 0) -> list[dict]:
    cursor = (
        discussions()
        .find({"channel_id": channel_id, "is_deleted": False})
        .sort("created_at", pymongo.DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    return list(cursor)


def soft_delete_discussion(discussion_id: str, deleted_by: int) -> bool:
    result = discussions().update_one(
        {"_id": ObjectId(discussion_id)},
        {"$set": {"is_deleted": True, "deleted_by": deleted_by, "deleted_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


def toggle_upvote_discussion(discussion_id: str, user_id: int) -> dict:
    """Returns {'upvotes': N, 'voted': bool}"""
    from bson import ObjectId
    key = f"upvote:{ObjectId(discussion_id)}"
    voter_field = f"voters.u{user_id}"
    
    doc = discussions().find_one({"_id": ObjectId(discussion_id)}, {"voters": 1, "upvotes": 1})
    if not doc:
        return {"upvotes": 0, "voted": False}
    
    voters = doc.get("voters", {})
    already_voted = voters.get(f"u{user_id}", False)
    
    if already_voted:
        discussions().update_one(
            {"_id": ObjectId(discussion_id)},
            {"$inc": {"upvotes": -1}, "$unset": {voter_field: ""}}
        )
        new_count = max(0, doc.get("upvotes", 0) - 1)
        return {"upvotes": new_count, "voted": False}
    else:
        discussions().update_one(
            {"_id": ObjectId(discussion_id)},
            {"$inc": {"upvotes": 1}, "$set": {voter_field: True}}
        )
        return {"upvotes": doc.get("upvotes", 0) + 1, "voted": True}


def get_user_voted_discussions(user_id: int, discussion_ids: list) -> set:
    """Return set of discussion_id strings the user has upvoted."""
    from bson import ObjectId
    voter_field = f"voters.u{user_id}"
    docs = discussions().find(
        {"_id": {"$in": [ObjectId(d) for d in discussion_ids]}, voter_field: True},
        {"_id": 1}
    )
    return {str(d["_id"]) for d in docs}


# ── Message helpers ────────────────────────────────────────────────────────────
def create_message(
    *,
    discussion_id: str,
    author_id: int,
    body: str,
    parent_message_id: str | None = None,
) -> str:
    """Post a message (or nested reply) to a discussion. Returns new ObjectId string."""
    now = datetime.now(timezone.utc)
    doc = {
        "discussion_id": discussion_id,
        "author_id": author_id,
        "body": body,
        "parent_message_id": parent_message_id,  # None = top-level
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
        "deleted_by_moderator": False,
        "upvotes": 0,
    }
    result = messages().insert_one(doc)
    # Bump reply_count on parent discussion
    discussions().update_one(
        {"_id": ObjectId(discussion_id)},
        {"$inc": {"reply_count": 1}, "$set": {"updated_at": now}},
    )
    return str(result.inserted_id)


def get_messages(discussion_id: str, limit: int = 200) -> list[dict]:
    cursor = (
        messages()
        .find({"discussion_id": discussion_id})
        .sort("created_at", pymongo.ASCENDING)
        .limit(limit)
    )
    return list(cursor)


def moderator_soft_delete_message(message_id: str, moderator_id: int) -> bool:
    """
    Soft-delete a message per moderation rules.
    The body is replaced on the frontend; we preserve the record in DB.
    """
    result = messages().update_one(
        {"_id": ObjectId(message_id)},
        {
            "$set": {
                "is_deleted": True,
                "deleted_by_moderator": True,
                "deleted_by": moderator_id,
                "deleted_at": datetime.now(timezone.utc),
            }
        },
    )
    return result.modified_count > 0


# ── Full-text search ───────────────────────────────────────────────────────────
def search_discussions(query: str, limit: int = 20) -> list[dict]:
    try:
        return list(
            discussions().find(
                {"$text": {"$search": query}, "is_deleted": False},
                {"score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
    except Exception:
        return []


def search_messages(query: str, limit: int = 20) -> list[dict]:
    try:
        return list(
            messages().find(
                {"$text": {"$search": query}, "is_deleted": False},
                {"score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
    except Exception:
        return []


def log_search(query: str, user_id: int, result_count: int) -> None:
    search_logs().insert_one(
        {
            "query": query,
            "user_id": user_id,
            "result_count": result_count,
            "created_at": datetime.now(timezone.utc),
        }
    )
