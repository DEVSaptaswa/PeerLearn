"""apps/channels/views.py"""
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Friendship, User
from utils.mongo_client import list_discussions, soft_delete_discussion
from .forms import ChannelCreateForm
from .models import (
    AccessRequest, Channel, ChannelInvite,
    ChannelMembership, ModerationLog,
)


def _get_membership(user, channel):
    return ChannelMembership.objects.filter(user=user, channel=channel).first()


def _is_moderator(user, channel):
    m = _get_membership(user, channel)
    return m is not None and m.is_moderator


def _refresh_member_count(channel):
    """Always recalculate from the actual membership rows — avoids drift."""
    count = ChannelMembership.objects.filter(channel=channel).count()
    Channel.objects.filter(pk=channel.pk).update(member_count=count)
    return count


# ── Channel list & create ──────────────────────────────────────────────────────
@login_required
def channel_list(request):
    channels   = Channel.objects.all().order_by("-member_count")
    joined_ids = ChannelMembership.objects.filter(user=request.user).values_list(
        "channel_id", flat=True
    )
    return render(
        request, "channels/channel_list.html",
        {"channels": channels, "joined_ids": set(joined_ids)},
    )


@login_required
def create_channel(request):
    form = ChannelCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        channel           = form.save(commit=False)
        channel.owner     = request.user
        channel.moderator = request.user
        # colour is submitted via the hidden #colorInput, not the form field
        color = request.POST.get("color", "#5865F2")
        VALID_COLORS = {c[0] for c in form.COLOR_CHOICES}
        channel.color = color if color in VALID_COLORS else "#5865F2"
        channel.save()
        ChannelMembership.objects.create(
            channel=channel, user=request.user,
            role=ChannelMembership.Role.OWNER, can_post=True,
        )
        _refresh_member_count(channel)
        messages.success(request, f"#{channel.name} created!")
        return redirect("channels:detail", slug=channel.slug)
    return render(request, "channels/create_channel.html", {"form": form})


# ── Channel detail ─────────────────────────────────────────────────────────────
@login_required
def channel_detail(request, slug):
    channel    = get_object_or_404(Channel, slug=slug)
    membership = _get_membership(request.user, channel)
    discussions = list_discussions(channel.pk, limit=40)

    access_request = None
    if channel.is_private and not membership:
        access_request = AccessRequest.objects.filter(
            channel=channel, user=request.user
        ).first()

    pending_requests = []
    if membership and membership.is_moderator:
        pending_requests = AccessRequest.objects.filter(
            channel=channel, status=AccessRequest.Status.PENDING
        ).select_related("user")

    # Always show accurate member count
    real_count = ChannelMembership.objects.filter(channel=channel).count()
    if real_count != channel.member_count:
        Channel.objects.filter(pk=channel.pk).update(member_count=real_count)
        channel.member_count = real_count

    context = {
        "channel":          channel,
        "membership":       membership,
        "discussions":      discussions,
        "is_moderator":     membership and membership.is_moderator,
        "can_post":         membership and membership.can_post,
        "access_request":   access_request,
        "pending_requests": pending_requests,
        "member_count":     real_count,
    }
    return render(request, "channels/channel_detail.html", context)


# ── Channel members list ───────────────────────────────────────────────────────
@login_required
def channel_members(request, slug):
    channel     = get_object_or_404(Channel, slug=slug)
    memberships = (
        ChannelMembership.objects.filter(channel=channel)
        .select_related("user", "user__profile")
        .order_by("role", "joined_at")
    )
    return render(request, "channels/channel_members.html", {
        "channel": channel,
        "memberships": memberships,
        "is_moderator": _is_moderator(request.user, channel),
    })


# ── Join / Leave ───────────────────────────────────────────────────────────────
@login_required
@require_POST
def join_channel(request, slug):
    channel = get_object_or_404(Channel, slug=slug)
    try:
        ChannelMembership.objects.create(
            channel=channel, user=request.user,
            role=ChannelMembership.Role.MEMBER,
            can_post=not channel.is_private,
        )
        count = _refresh_member_count(channel)
        return JsonResponse({"joined": True, "member_count": count})
    except IntegrityError:
        return JsonResponse({"joined": False, "error": "Already a member."})


@login_required
@require_POST
def leave_channel(request, slug):
    channel  = get_object_or_404(Channel, slug=slug)
    deleted, _ = ChannelMembership.objects.filter(
        channel=channel, user=request.user
    ).delete()
    count = _refresh_member_count(channel) if deleted else channel.member_count
    return JsonResponse({"left": bool(deleted), "member_count": count})


# ── Access request workflow ────────────────────────────────────────────────────
@login_required
@require_POST
def request_access(request, slug):
    channel = get_object_or_404(Channel, slug=slug, privacy=Channel.Privacy.PRIVATE)
    body    = json.loads(request.body)
    try:
        ar, created = AccessRequest.objects.get_or_create(
            channel=channel, user=request.user,
            defaults={"message": body.get("message", "")},
        )
        return JsonResponse({"requested": True, "id": ar.pk})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
@require_POST
def review_access_request(request, request_id):
    ar      = get_object_or_404(AccessRequest, pk=request_id)
    channel = ar.channel
    if not _is_moderator(request.user, channel):
        return JsonResponse({"error": "Forbidden."}, status=403)

    body   = json.loads(request.body)
    action = body.get("action")

    if action == "approve":
        ar.status      = AccessRequest.Status.APPROVED
        ar.reviewed_by = request.user
        ar.save()
        ChannelMembership.objects.update_or_create(
            channel=channel, user=ar.user,
            defaults={"role": ChannelMembership.Role.MEMBER, "can_post": True},
        )
        count = _refresh_member_count(channel)   # ← update count immediately
        ModerationLog.objects.create(
            channel=channel, moderator=request.user,
            action=ModerationLog.Action.APPROVE_ACCESS, target_user=ar.user,
        )
        return JsonResponse({"status": ar.status, "member_count": count})

    elif action == "deny":
        ar.status      = AccessRequest.Status.DENIED
        ar.reviewed_by = request.user
        ar.save()
        ModerationLog.objects.create(
            channel=channel, moderator=request.user,
            action=ModerationLog.Action.DENY_ACCESS, target_user=ar.user,
        )
        return JsonResponse({"status": ar.status})

    return JsonResponse({"error": "Invalid action."}, status=400)


# ── Invite a friend ────────────────────────────────────────────────────────────
@login_required
@require_POST
def invite_friend(request, slug):
    channel = get_object_or_404(Channel, slug=slug)
    if not _get_membership(request.user, channel):
        return JsonResponse({"error": "You must be a member to invite."}, status=403)

    body      = json.loads(request.body)
    friend_id = body.get("user_id")
    friend    = get_object_or_404(User, pk=friend_id)

    if not Friendship.are_friends(request.user, friend):
        return JsonResponse({"error": "Not a friend."}, status=400)

    try:
        invite, created = ChannelInvite.objects.get_or_create(
            channel=channel, invited_user=friend,
            defaults={"invited_by": request.user},
        )
        return JsonResponse({"invited": True, "created": created})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# ── Moderator: soft-delete a discussion ───────────────────────────────────────
@login_required
@require_POST
def mod_delete_discussion(request, slug):
    channel = get_object_or_404(Channel, slug=slug)
    if not _is_moderator(request.user, channel):
        return JsonResponse({"error": "Forbidden."}, status=403)

    body          = json.loads(request.body)
    discussion_id = body.get("discussion_id")
    soft_delete_discussion(discussion_id, deleted_by=request.user.pk)
    ModerationLog.objects.create(
        channel=channel, moderator=request.user,
        action=ModerationLog.Action.DELETE_DISCUSSION,
        target_mongo_id=discussion_id,
    )
    return JsonResponse({"deleted": True})


# ── Channel search API ─────────────────────────────────────────────────────────
@login_required
def search_channels_api(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 1:
        return JsonResponse({"channels": []})
    qs = Channel.objects.filter(
        Q(name__icontains=q) | Q(description__icontains=q)
    )[:10]
    return JsonResponse({"channels": [{
        "id": c.pk, "name": c.name, "slug": c.slug,
        "icon": c.icon, "color": c.color,
        "privacy": c.privacy, "member_count": c.member_count,
    } for c in qs]})
