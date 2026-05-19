# Generated migration for apps.accounts
from django.db import migrations, models
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False)),
                ("username", models.CharField(
                    error_messages={"unique": "A user with that username already exists."},
                    max_length=150, unique=True,
                    validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    verbose_name="username",
                )),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("is_staff", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="email address")),
                ("bio", models.TextField(blank=True, default="")),
                ("display_name", models.CharField(blank=True, max_length=60)),
                ("groups", models.ManyToManyField(
                    blank=True, related_name="user_set", related_query_name="user",
                    to="auth.group", verbose_name="groups",
                )),
                ("user_permissions", models.ManyToManyField(
                    blank=True, related_name="user_set", related_query_name="user",
                    to="auth.permission", verbose_name="user permissions",
                )),
            ],
            options={
                "verbose_name": "User",
                "db_table": "auth_users",
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("avatar", models.ImageField(blank=True, null=True, upload_to="avatars/")),
                ("avatar_color", models.CharField(default="#5865F2", max_length=7)),
                ("threads_started", models.PositiveIntegerField(default=0)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="profile",
                    to="accounts.user",
                )),
            ],
            options={"db_table": "user_profiles"},
        ),
        migrations.CreateModel(
            name="Friendship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("accepted", "Accepted"), ("blocked", "Blocked")],
                    default="pending", max_length=10,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("from_user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sent_friend_requests",
                    to="accounts.user",
                )),
                ("to_user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="received_friend_requests",
                    to="accounts.user",
                )),
            ],
            options={
                "verbose_name_plural": "Friendships",
                "db_table": "friendships",
            },
        ),
        migrations.AlterUniqueTogether(
            name="friendship",
            unique_together={("from_user", "to_user")},
        ),
    ]
