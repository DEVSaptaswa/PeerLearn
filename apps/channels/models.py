"""
apps/channels/models.py
MySQL models: Channel, ChannelMembership, AccessRequest, ChannelInvite, ModerationLog
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User


class Channel(models.Model):
    class Privacy(models.TextChoices):
        PUBLIC = "public", _("Public")
        PRIVATE = "private", _("Private")  # view-only; post requires approval

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=2, default="📚")  # emoji shorthand
    color = models.CharField(max_length=7, default="#5865F2")  # hex accent
    privacy = models.CharField(max_length=10, choices=Privacy.choices, default=Privacy.PUBLIC)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="owned_channels")
    moderator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="moderated_channels"
    )
    member_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "channels"
        ordering = ["-member_count"]

    def __str__(self):
        return f"#{self.name}"

    @property
    def is_private(self) -> bool:
        return self.privacy == self.Privacy.PRIVATE


class ChannelMembership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member", _("Member")
        MODERATOR = "moderator", _("Moderator")
        OWNER = "owner", _("Owner")

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="channel_memberships")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.MEMBER)
    can_post = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "channel_memberships"
        unique_together = ("channel", "user")

    def __str__(self):
        return f"{self.user.username} in #{self.channel.name} [{self.role}]"

    @property
    def is_moderator(self) -> bool:
        return self.role in (self.Role.MODERATOR, self.Role.OWNER)


class AccessRequest(models.Model):
    """Request to post in a private channel."""
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        DENIED = "denied", _("Denied")

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="access_requests")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="access_requests")
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_requests"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "access_requests"
        unique_together = ("channel", "user")


class ChannelInvite(models.Model):
    """Invite a friend into a channel."""
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="invites")
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invites")
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_invites")
    accepted = models.BooleanField(null=True)  # None=pending, True=accepted, False=declined
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "channel_invites"
        unique_together = ("channel", "invited_user")


class ModerationLog(models.Model):
    """Immutable audit trail for every moderation action."""
    class Action(models.TextChoices):
        DELETE_MESSAGE = "delete_message", _("Delete Message")
        DELETE_DISCUSSION = "delete_discussion", _("Delete Discussion")
        APPROVE_ACCESS = "approve_access", _("Approve Access")
        DENY_ACCESS = "deny_access", _("Deny Access")
        BAN_USER = "ban_user", _("Ban User")

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="mod_logs")
    moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="mod_actions")
    action = models.CharField(max_length=20, choices=Action.choices)
    target_mongo_id = models.CharField(max_length=24, blank=True)  # Mongo ObjectId as string
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="mod_targets"
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "moderation_logs"
        ordering = ["-created_at"]
