"""
apps/discussions/views.py
All discussion & message persistence goes to MongoDB.
Channel membership enforcement is validated against MySQL.
"""
import json
from bson import ObjectId
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.channels.models import Channel, ChannelMembership, ModerationLog
from utils.mongo_client import (
    create_discussion, create_message, get_discussion, get_messages,
    list_discussions, moderator_soft_delete_message, upvote_discussion,
)

DELETED_MESSAGE_PLACEHOLDER = (
    "🚫 This message was removed by the moderator for violating community guidelines."
)


def _user_avatar(profile):
    """Return avatar URL or None."""
    if profile and profile.avatar:
        try:
            return profile.avatar.url
        except Exception:
            return None
    return None


def _serialize_discussion(d: dict) -> dict:
    return {
        "id": str(d["_id"]),
        "channel_id": d["channel_id"],
        "author_id": d["author_id"],
        "title": d.get("title", ""),
        "body": d.get("body", ""),
        "upvotes": d.get("upvotes", 0),
        "reply_count": d.get("reply_count", 0),
        "created_at": d["created_at"].isoformat(),
        "is_deleted": d.get("is_deleted", False),
    }


def _serialize_message(m: dict) -> dict:
    is_deleted = m.get("is_deleted", False)
    mod_deleted = m.get("deleted_by_moderator", False)
    body = DELETED_MESSAGE_PLACEHOLDER if (is_deleted and mod_deleted) else m.get("body", "")
    return {
        "id": str(m["_id"]),
        "discussion_id": m["discussion_id"],
        "author_id": m["author_id"],
        "body": body,
        "parent_message_id": m.get("parent_message_id"),
        "upvotes": m.get("upvotes", 0),
        "created_at": m["created_at"].isoformat(),
        "is_deleted": is_deleted,
        "deleted_by_moderator": mod_deleted,
    }


# ── Discussion detail page ─────────────────────────────────────────────────────
@login_required
def discussion_detail(request, channel_slug, discussion_id):
    channel = get_object_or_404(Channel, slug=channel_slug)
    discussion = get_discussion(discussion_id)
    if not discussion or discussion["channel_id"] != channel.pk:
        from django.http import Http404
        raise Http404("Discussion not found.")

    membership = ChannelMembership.objects.filter(user=request.user, channel=channel).first()
    msgs = get_messages(discussion_id)

    author_ids = list({m["author_id"] for m in msgs} | {discussion["author_id"]})
    users = {u.pk: u for u in User.objects.filter(pk__in=author_ids).select_related("profile")}

    serialized_msgs = []
    for m in msgs:
        sm = _serialize_message(m)
        author = users.get(m["author_id"])
        if author:
            p = getattr(author, "profile", None)
            sm["author_username"] = author.username
            sm["author_display"] = author.get_display_name()
            sm["author_color"] = p.avatar_color if p else "#5865F2"
            sm["author_initial"] = author.get_avatar_initial()
            sm["author_avatar"] = _user_avatar(p)
        serialized_msgs.append(sm)

    disc_author = users.get(discussion["author_id"])
    context = {
        "channel": channel,
        "discussion": discussion,
        "discussion_id": discussion_id,
        "messages": serialized_msgs,
        "membership": membership,
        "is_moderator": membership and membership.is_moderator,
        "can_post": membership and membership.can_post,
        "disc_author": disc_author,
    }
    return render(request, "discussions/discussion_detail.html", context)


# ── Thread list for a channel (JSON / AJAX) ────────────────────────────────────
@login_required
def discussions_api(request, channel_slug):
    channel = get_object_or_404(Channel, slug=channel_slug)
    skip  = int(request.GET.get("skip",  0))
    limit = int(request.GET.get("limit", 20))
    discs = list_discussions(channel.pk, limit=limit, skip=skip)

    author_ids = list({d["author_id"] for d in discs})
    users = {u.pk: u for u in User.objects.filter(pk__in=author_ids).select_related("profile")}

    result = []
    for d in discs:
        sd = _serialize_discussion(d)
        author = users.get(d["author_id"])
        if author:
            p = getattr(author, "profile", None)
            sd["author_username"]  = author.username
            sd["author_display"]   = author.get_display_name()
            sd["author_color"]     = p.avatar_color if p else "#5865F2"
            sd["author_initial"]   = author.get_avatar_initial()
            sd["author_avatar_url"] = _user_avatar(p)   # ← was missing
        result.append(sd)

    return JsonResponse({"discussions": result, "has_more": len(discs) == limit})


# ── Create discussion ──────────────────────────────────────────────────────────
@login_required
@require_POST
def create_discussion_view(request, channel_slug):
    channel = get_object_or_404(Channel, slug=channel_slug)
    membership = ChannelMembership.objects.filter(user=request.user, channel=channel).first()
    if not membership or not membership.can_post:
        return JsonResponse({"error": "You do not have posting rights in this channel."}, status=403)

    body = json.loads(request.body)
    title   = body.get("title", "").strip()
    content = body.get("body",  "").strip()
    if not title or not content:
        return JsonResponse({"error": "Title and body are required."}, status=400)

    disc_id = create_discussion(
        channel_id=channel.pk,
        author_id=request.user.pk,
        title=title,
        body=content,
        is_private_channel=channel.is_private,
    )

    from django.db.models import F
    from apps.accounts.models import Profile
    Profile.objects.filter(user=request.user).update(threads_started=F("threads_started") + 1)

    return JsonResponse({"discussion_id": disc_id, "title": title})


# ── Post a message ─────────────────────────────────────────────────────────────
@login_required
@require_POST
def post_message(request, channel_slug, discussion_id):
    channel = get_object_or_404(Channel, slug=channel_slug)
    membership = ChannelMembership.objects.filter(user=request.user, channel=channel).first()
    if not membership or not membership.can_post:
        return JsonResponse({"error": "Posting not permitted."}, status=403)

    body   = json.loads(request.body)
    text   = body.get("body", "").strip()
    parent = body.get("parent_message_id", None)
    if not text:
        return JsonResponse({"error": "Message cannot be empty."}, status=400)

    msg_id = create_message(
        discussion_id=discussion_id,
        author_id=request.user.pk,
        body=text,
        parent_message_id=parent,
    )

    p = getattr(request.user, "profile", None)
    return JsonResponse({
        "id":              msg_id,
        "body":            text,
        "author_id":       request.user.pk,
        "author_username": request.user.username,
        "author_display":  request.user.get_display_name(),
        "author_color":    p.avatar_color if p else "#5865F2",
        "author_initial":  request.user.get_avatar_initial(),
        "author_avatar":   _user_avatar(p),
        "parent_message_id": parent,
    })


# ── Upvote a discussion ────────────────────────────────────────────────────────
@login_required
@require_POST
def upvote_discussion_view(request, discussion_id):
    upvote_discussion(discussion_id)
    return JsonResponse({"ok": True})


# ── Moderator: soft-delete a message ──────────────────────────────────────────
@login_required
@require_POST
def mod_delete_message(request, channel_slug, message_id):
    channel    = get_object_or_404(Channel, slug=channel_slug)
    membership = ChannelMembership.objects.filter(user=request.user, channel=channel).first()
    if not membership or not membership.is_moderator:
        return JsonResponse({"error": "Forbidden."}, status=403)

    success = moderator_soft_delete_message(message_id, moderator_id=request.user.pk)
    if success:
        body = json.loads(request.body) if request.body else {}
        ModerationLog.objects.create(
            channel=channel,
            moderator=request.user,
            action=ModerationLog.Action.DELETE_MESSAGE,
            target_mongo_id=message_id,
            reason=body.get("reason", ""),
        )
    return JsonResponse({"deleted": success, "placeholder": DELETED_MESSAGE_PLACEHOLDER})


# ── Unified search (MySQL + MongoDB) ──────────────────────────────────────────
@login_required
def unified_search(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"users": [], "channels": [], "discussions": [], "messages": []})

    from django.db.models import Q as DQ
    from utils.mongo_client import search_discussions, search_messages, log_search

    user_qs = (
        User.objects.filter(DQ(username__icontains=q) | DQ(display_name__icontains=q))
        .exclude(pk=request.user.pk)
        .select_related("profile")[:5]
    )
    users_data = [{
        "id": u.pk,
        "username": u.username,
        "display_name": u.get_display_name(),
        "avatar_color": getattr(u.profile, "avatar_color", "#5865F2"),
        "initial": u.get_avatar_initial(),
        "avatar_url": _user_avatar(getattr(u, "profile", None)),
    } for u in user_qs]

    channel_qs = Channel.objects.filter(
        DQ(name__icontains=q) | DQ(description__icontains=q)
    )[:5]
    channels_data = [{
        "id": c.pk, "name": c.name, "slug": c.slug,
        "icon": c.icon, "color": c.color,
    } for c in channel_qs]

    mongo_discs = search_discussions(q, limit=5)
    discussions_data = [{
        "id": str(d["_id"]), "title": d.get("title", ""), "channel_id": d.get("channel_id"),
    } for d in mongo_discs]

    mongo_msgs = search_messages(q, limit=5)
    messages_data = [{
        "id": str(m["_id"]), "body": m.get("body", "")[:120], "discussion_id": m.get("discussion_id"),
    } for m in mongo_msgs]

    total = len(users_data) + len(channels_data) + len(discussions_data) + len(messages_data)
    log_search(q, request.user.pk, total)

    return JsonResponse({
        "users": users_data, "channels": channels_data,
        "discussions": discussions_data, "messages": messages_data,
    })
