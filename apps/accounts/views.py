"""apps/accounts/views.py"""
import json
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import models as db_models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from utils.redis_client import get_bulk_statuses, set_user_status, get_user_status
from .forms import LoginForm, ProfileEditForm, RegisterForm
from .models import Friendship, User


# ── Auth ───────────────────────────────────────────────────────────────────────
def register_view(request):
    if request.user.is_authenticated:
        return redirect("/")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome aboard, {user.get_display_name()}! 🎉")
        return redirect("/")
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next", "/"))
    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    return redirect("/accounts/login/")


# ── Profile ────────────────────────────────────────────────────────────────────
@login_required
def profile_view(request, username=None):
    if username:
        target = get_object_or_404(User, username=username)
    else:
        target = request.user

    is_own = target == request.user

    # Friendship state — also track direction so we know whether to show
    # "Accept/Reject" (they sent to us) vs "Pending" (we sent to them)
    friendship_status   = None
    friendship_id       = None
    i_sent_the_request  = False
    if not is_own:
        fs = Friendship.objects.filter(
            db_models.Q(from_user=request.user, to_user=target)
            | db_models.Q(from_user=target, to_user=request.user)
        ).first()
        if fs:
            friendship_status  = fs.status
            friendship_id      = fs.pk
            i_sent_the_request = (fs.from_user_id == request.user.pk)

    from utils.mongo_client import discussions as mongo_discussions
    try:
        thread_count = mongo_discussions().count_documents(
            {"author_id": target.pk, "is_deleted": False}
        )
    except Exception:
        thread_count = 0

    from apps.channels.models import ChannelMembership
    channel_count = ChannelMembership.objects.filter(user=target).count()

    context = {
        "target":               target,
        "is_own":               is_own,
        "friendship_status":    friendship_status,
        "friendship_id":        friendship_id,
        "i_sent_the_request":   i_sent_the_request,
        "thread_count":         thread_count,
        "channel_count":        channel_count,
        "friends":              Friendship.get_friends(target)[:6],
        "friend_count":         target.friend_count,
    }
    return render(request, "accounts/profile.html", context)


@login_required
def edit_profile_view(request):
    form = ProfileEditForm(
        request.POST or None,
        request.FILES or None,
        instance=request.user.profile,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/edit_profile.html", {"form": form})


# ── Friendship API ─────────────────────────────────────────────────────────────
@login_required
@require_POST
def send_friend_request(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        return JsonResponse({"error": "Cannot add yourself."}, status=400)

    fs, created = Friendship.objects.get_or_create(
        from_user=request.user,
        to_user=target,
        defaults={"status": Friendship.Status.PENDING},
    )
    if not created and fs.status == Friendship.Status.BLOCKED:
        return JsonResponse({"error": "Action not allowed."}, status=403)

    return JsonResponse({"status": fs.status, "created": created, "friendship_id": fs.pk})


@login_required
@require_POST
def respond_friend_request(request, friendship_id):
    fs     = get_object_or_404(Friendship, pk=friendship_id, to_user=request.user)
    body   = json.loads(request.body)
    action = body.get("action")   # "accept" | "reject"

    if action == "accept":
        fs.status = Friendship.Status.ACCEPTED
        fs.save(update_fields=["status", "updated_at"])
        return JsonResponse({"status": "accepted"})
    elif action == "reject":
        fs.delete()
        return JsonResponse({"status": "removed"})
    return JsonResponse({"error": "Invalid action."}, status=400)


# ── Status toggle ──────────────────────────────────────────────────────────────
@login_required
@require_POST
def set_status_view(request):
    body   = json.loads(request.body)
    status = body.get("status", "clear")
    if status not in ("invisible", "dnd", "clear"):
        return JsonResponse({"error": "Invalid status."}, status=400)
    set_user_status(request.user.pk, status)
    resolved = get_user_status(request.user.pk)
    return JsonResponse({"ok": True, "status": status, "resolved": resolved})


# ── Friend list with live statuses (JSON — polled by sidebar JS) ───────────────
@login_required
def friends_status_api(request):
    friends  = Friendship.get_friends(request.user)
    ids      = [f.pk for f in friends]
    statuses = get_bulk_statuses(ids)

    data = []
    for friend in friends:
        p = getattr(friend, "profile", None)
        data.append({
            "id":           friend.pk,
            "username":     friend.username,
            "display_name": friend.get_display_name(),
            "avatar_url":   p.get_avatar_url() if p else None,
            "avatar_color": p.avatar_color if p else "#5865F2",
            "initial":      friend.get_avatar_initial(),
            "status":       statuses.get(friend.pk, "offline"),
        })

    order = {"active": 0, "away": 1, "offline": 2}
    data.sort(key=lambda x: order.get(x["status"], 3))
    return JsonResponse({"friends": data})


# ── Pending friend requests (JSON) ────────────────────────────────────────────
@login_required
def friend_requests_api(request):
    qs = (
        Friendship.objects.filter(to_user=request.user, status=Friendship.Status.PENDING)
        .select_related("from_user", "from_user__profile")
    )
    data = []
    for fs in qs:
        u = fs.from_user
        p = getattr(u, "profile", None)
        data.append({
            "friendship_id": fs.pk,
            "id":            u.pk,
            "username":      u.username,
            "display_name":  u.get_display_name(),
            "avatar_url":    p.get_avatar_url() if p else None,
            "avatar_color":  p.avatar_color if p else "#5865F2",
            "initial":       u.get_avatar_initial(),
        })
    return JsonResponse({"requests": data, "count": len(data)})


# ── User search ───────────────────────────────────────────────────────────────
@login_required
def search_users_api(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"users": []})
    users = (
        User.objects.filter(
            db_models.Q(username__icontains=q) | db_models.Q(display_name__icontains=q)
        )
        .exclude(pk=request.user.pk)
        .select_related("profile")[:10]
    )
    return JsonResponse({"users": [{
        "id":           u.pk,
        "username":     u.username,
        "display_name": u.get_display_name(),
        "avatar_color": getattr(u.profile, "avatar_color", "#5865F2"),
        "initial":      u.get_avatar_initial(),
    } for u in users]})


# ── Profile mini (friend modal popup) ─────────────────────────────────────────
@login_required
def profile_mini_api(request, user_id):
    from apps.channels.models import ChannelMembership
    user = get_object_or_404(User, pk=user_id)
    try:
        from utils.mongo_client import discussions as mongo_discussions
        thread_count = mongo_discussions().count_documents(
            {"author_id": user.pk, "is_deleted": False}
        )
    except Exception:
        thread_count = 0
    channel_count = ChannelMembership.objects.filter(user=user).count()
    p = getattr(user, "profile", None)
    return JsonResponse({
        "id":           user.pk,
        "username":     user.username,
        "display_name": user.get_display_name(),
        "bio":          user.bio or "",
        "avatar_url":   p.get_avatar_url() if p else None,
        "avatar_color": p.avatar_color if p else "#5865F2",
        "initial":      user.get_avatar_initial(),
        "friend_count": user.friend_count,
        "thread_count": thread_count,
        "channel_count": channel_count,
    })
