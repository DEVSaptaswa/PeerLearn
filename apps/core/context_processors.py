"""apps/core/context_processors.py"""
from apps.accounts.models import Friendship
from apps.channels.models import Channel, ChannelMembership
from utils.redis_client import get_bulk_statuses, get_user_status


def sidebar_context(request):
    """Injects sidebar data + current user's resolved status into every template."""
    if not request.user.is_authenticated:
        return {}
    try:
        # ── Left sidebar: joined channels ──────────────────────────────────────
        memberships = (
            ChannelMembership.objects.filter(user=request.user)
            .select_related("channel")
            .order_by("channel__name")
        )
        joined_channels = [m.channel for m in memberships]

        # ── Right sidebar: accepted friends with live statuses ─────────────────
        friends     = list(Friendship.get_friends(request.user))
        friend_ids  = [f.pk for f in friends]
        statuses    = get_bulk_statuses(friend_ids)

        friends_with_status = []
        for friend in friends:
            p = getattr(friend, "profile", None)
            friends_with_status.append({
                "user":         friend,
                "profile":      p,
                "status":       statuses.get(friend.pk, "offline"),
                "avatar_color": p.avatar_color if p else "#5865F2",
                "initial":      friend.get_avatar_initial(),
                "avatar_url":   p.get_avatar_url() if p else None,
            })

        order = {"active": 0, "away": 1, "offline": 2}
        friends_with_status.sort(key=lambda x: order.get(x["status"], 3))

        # ── Right sidebar: incoming friend requests ────────────────────────────
        pending_qs = (
            Friendship.objects.filter(to_user=request.user, status=Friendship.Status.PENDING)
            .select_related("from_user", "from_user__profile")
        )
        pending_requests_list = []
        for fs in pending_qs:
            u = fs.from_user
            p = getattr(u, "profile", None)
            pending_requests_list.append({
                "friendship_id": fs.pk,
                "user":         u,
                "avatar_color": p.avatar_color if p else "#5865F2",
                "initial":      u.get_avatar_initial(),
                "avatar_url":   p.get_avatar_url() if p else None,
            })

        # ── My own resolved status (for nav dot + dropdown highlight) ──────────
        my_status = get_user_status(request.user.pk)

        return {
            "sidebar_channels":        joined_channels,
            "sidebar_friends":         friends_with_status,
            "sidebar_friend_requests": pending_requests_list,
            "pending_friend_requests": len(pending_requests_list),
            "my_status":               my_status,
        }
    except Exception:
        return {
            "sidebar_channels":        [],
            "sidebar_friends":         [],
            "sidebar_friend_requests": [],
            "pending_friend_requests": 0,
            "my_status":               "offline",
        }
