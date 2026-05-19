"""apps/core/views.py"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from apps.channels.models import Channel, ChannelMembership
from utils.mongo_client import list_discussions


@login_required
def home(request):
    """
    Main feed: shows threads from all channels the user has joined,
    falling back to trending public channels if they've joined none.
    """
    memberships = ChannelMembership.objects.filter(user=request.user).select_related("channel")
    joined_channels = [m.channel for m in memberships]

    feed_discussions = []
    for channel in joined_channels[:5]:  # limit for performance
        discs = list_discussions(channel.pk, limit=10)
        for d in discs:
            d["disc_id"] = str(d["_id"])
            d["channel_name"] = channel.name
            d["channel_slug"] = channel.slug
            d["channel_color"] = channel.color
        feed_discussions.extend(discs)

    # Sort combined feed by created_at descending
    feed_discussions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    feed_discussions = feed_discussions[:30]

    # Trending channels (for discovery)
    trending = Channel.objects.filter(privacy=Channel.Privacy.PUBLIC).order_by("-member_count")[:8]

    context = {
        "feed_discussions": feed_discussions,
        "trending_channels": trending,
        "joined_channels": joined_channels,
    }
    return render(request, "index.html", context)
