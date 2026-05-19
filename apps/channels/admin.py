"""apps/channels/admin.py"""
from django.contrib import admin
from .models import Channel, ChannelMembership, AccessRequest, ChannelInvite, ModerationLog


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display  = ("name", "privacy", "owner", "moderator", "member_count", "created_at")
    list_filter   = ("privacy",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ChannelMembership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("channel", "user", "role", "can_post", "joined_at")
    list_filter  = ("role",)


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = ("channel", "user", "status", "created_at")
    list_filter  = ("status",)


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display  = ("channel", "moderator", "action", "target_mongo_id", "created_at")
    list_filter   = ("action",)
    readonly_fields = ("created_at",)
