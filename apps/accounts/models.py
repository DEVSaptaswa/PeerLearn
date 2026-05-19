"""
apps/accounts/models.py
MySQL-backed relational models: custom User, Profile, Friendship
"""
import os
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


def avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return os.path.join("avatars", f"user_{instance.user.pk}.{ext}")


class User(AbstractUser):
    """Extended auth user — stored in MySQL."""

    email = models.EmailField(_("email address"), unique=True)
    bio = models.TextField(blank=True, default="")
    display_name = models.CharField(max_length=60, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "auth_users"
        verbose_name = "User"

    def get_display_name(self) -> str:
        return self.display_name or self.username

    def get_avatar_initial(self) -> str:
        name = self.get_display_name()
        return name[0].upper() if name else "?"

    @property
    def friend_count(self) -> int:
        return Friendship.objects.filter(
            models.Q(from_user=self) | models.Q(to_user=self),
            status=Friendship.Status.ACCEPTED,
        ).count()

    @property
    def thread_count(self) -> int:
        """Reads from MongoDB via the discussions app — cached on Profile."""
        return getattr(self, "_thread_count", 0)


class Profile(models.Model):
    """One-to-one MySQL profile extending User."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    # Avatar background colour — generated at signup from username hash
    avatar_color = models.CharField(max_length=7, default="#5865F2")
    threads_started = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_profiles"

    def __str__(self):
        return f"Profile({self.user.username})"

    def get_avatar_url(self) -> str | None:
        if self.avatar:
            return self.avatar.url
        return None

    def generate_avatar_color(self) -> str:
        """Deterministic colour from username — used as CSS bg for initial avatar."""
        PALETTE = [
            "#5865F2", "#EB459E", "#57F287", "#FEE75C",
            "#ED4245", "#9B59B6", "#E67E22", "#1ABC9C",
        ]
        idx = sum(ord(c) for c in self.user.username) % len(PALETTE)
        return PALETTE[idx]


class Friendship(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        BLOCKED = "blocked", _("Blocked")

    from_user = models.ForeignKey(
        User, related_name="sent_friend_requests", on_delete=models.CASCADE
    )
    to_user = models.ForeignKey(
        User, related_name="received_friend_requests", on_delete=models.CASCADE
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "friendships"
        unique_together = ("from_user", "to_user")
        verbose_name_plural = "Friendships"

    def __str__(self):
        return f"{self.from_user} → {self.to_user} [{self.status}]"

    @classmethod
    def are_friends(cls, user_a, user_b) -> bool:
        return cls.objects.filter(
            models.Q(from_user=user_a, to_user=user_b) | models.Q(from_user=user_b, to_user=user_a),
            status=cls.Status.ACCEPTED,
        ).exists()

    @classmethod
    def get_friends(cls, user) -> models.QuerySet:
        """Return User queryset of accepted friends."""
        from_ids = cls.objects.filter(from_user=user, status=cls.Status.ACCEPTED).values_list("to_user_id", flat=True)
        to_ids = cls.objects.filter(to_user=user, status=cls.Status.ACCEPTED).values_list("from_user_id", flat=True)
        all_ids = list(from_ids) + list(to_ids)
        return User.objects.filter(pk__in=all_ids).select_related("profile")
