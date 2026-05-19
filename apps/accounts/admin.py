"""apps/accounts/admin.py"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile, Friendship


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "display_name", "is_staff", "date_joined")
    search_fields = ("email", "username", "display_name")
    ordering = ("-date_joined",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Extended", {"fields": ("bio", "display_name")}),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ("user", "avatar_color", "threads_started", "joined_at")
    search_fields = ("user__username", "user__email")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display  = ("from_user", "to_user", "status", "created_at")
    list_filter   = ("status",)
    search_fields = ("from_user__username", "to_user__username")
