"""
apps/core/management/commands/seed_data.py
Populate the database with realistic sample data for development.
Usage: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify


CHANNELS = [
    {"name": "python",          "icon": "🐍", "color": "#3776AB",
     "desc": "All things Python — from beginner scripts to advanced architectures."},
    {"name": "linear-algebra",  "icon": "📐", "color": "#E67E22",
     "desc": "Vectors, matrices, eigenvalues, and more."},
    {"name": "web-dev",         "icon": "🌐", "color": "#57F287",
     "desc": "HTML, CSS, JavaScript, frameworks and best practices."},
    {"name": "machine-learning","icon": "🤖", "color": "#9B59B6",
     "desc": "ML algorithms, datasets, model training, and deployment."},
    {"name": "algorithms",      "icon": "⚙️",  "color": "#ED4245",
     "desc": "Problem solving, competitive programming, LeetCode strategies."},
    {"name": "databases",       "icon": "🗄️",  "color": "#FEE75C",
     "desc": "SQL, NoSQL, indexing, query optimisation."},
    {"name": "career-advice",   "icon": "💼", "color": "#1ABC9C",
     "desc": "Resumes, interviews, portfolio tips and career growth."},
]

DISCUSSIONS = [
    ("python", "What's the best way to learn decorators?",
     "I've been writing Python for 6 months and decorators still confuse me. "
     "Any good resources or mental models that helped it finally click?"),
    ("python", "Poetry vs pip + venv in 2024",
     "Curious what the community is using for dependency management. "
     "I switched to Poetry last year and haven't looked back — but I keep seeing pip-tools mentioned."),
    ("linear-algebra", "Intuition behind the determinant",
     "I can compute determinants all day but I still don't *feel* what they represent geometrically. "
     "Every explanation I find goes straight to cofactor expansion. Can someone explain it visually?"),
    ("web-dev", "CSS Grid vs Flexbox — when to use which?",
     "I know both fairly well but I still second-guess myself every time I start a new layout. "
     "What's your decision framework? Do you default to one and reach for the other only for specific cases?"),
    ("machine-learning", "Overfitting on small datasets — what's your go-to fix?",
     "Working with ~500 labelled examples. Model trains to 99% accuracy but validation hovers around 60%. "
     "I've tried dropout and L2 regularisation. What else should I try before collecting more data?"),
    ("algorithms", "How to approach dynamic programming problems",
     "Every time I see a DP problem in an interview my mind goes blank. "
     "Is there a systematic approach — like, a checklist you go through — that helped it click for you?"),
    ("databases", "When should you denormalise?",
     "I keep hearing 'normalise until it hurts, then denormalise' but where exactly is that threshold? "
     "How do you decide in practice, especially for read-heavy workloads?"),
]

# Extra replies seeded into the first discussion of each channel
SAMPLE_REPLIES = [
    "Great question! This is something I struggled with too at first.",
    "I'd recommend checking out Real Python's article on this — it's the clearest explanation I've found.",
    "The key insight for me was thinking about it as a function that wraps another function.",
    "Once you understand closures, decorators make much more sense. Start there!",
    "Here's a minimal example that might help: `def my_decorator(func): ...`",
]


class Command(BaseCommand):
    help = "Seed the database with sample channels, users, and discussions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear existing seeded data before re-seeding.",
        )

    def handle(self, *args, **options):
        from apps.accounts.models import User, Profile
        from apps.channels.models import Channel, ChannelMembership
        from utils.mongo_client import create_discussion, create_message, list_discussions

        self.stdout.write(self.style.MIGRATE_HEADING("\n🌱  PeerLearn — Seeding sample data\n"))

        # ── 1. Create channels ────────────────────────────────────────────────
        channels_map = {}
        for ch in CHANNELS:
            channel, created = Channel.objects.get_or_create(
                slug=slugify(ch["name"]),
                defaults={
                    "name": ch["name"],
                    "icon": ch["icon"],
                    "color": ch["color"],
                    "description": ch["desc"],
                    "privacy": Channel.Privacy.PUBLIC,
                },
            )
            channels_map[ch["name"]] = channel
            if created:
                self.stdout.write(f"  ✔  Channel #{channel.name} created")
            else:
                self.stdout.write(f"  –  Channel #{channel.name} already exists")

        # ── 2. Create admin superuser ─────────────────────────────────────────
        admin_email = "admin@peerlearn.dev"
        admin, created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                "username": "admin",
                "display_name": "PeerLearn Admin",
                "bio": "Platform administrator and community moderator.",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(f"  ✔  Superuser created: {admin_email} / admin123")
        else:
            self.stdout.write(f"  –  Superuser already exists: {admin_email}")

        # ── 3. Create sample community user ──────────────────────────────────
        user_email = "learner@peerlearn.dev"
        learner, created = User.objects.get_or_create(
            email=user_email,
            defaults={
                "username": "learner",
                "display_name": "Eager Learner",
                "bio": "Always curious, always learning. Passionate about Python and ML.",
            },
        )
        if created:
            learner.set_password("learner123")
            learner.save()
            self.stdout.write(f"  ✔  Sample user created: {user_email} / learner123")
        else:
            self.stdout.write(f"  –  Sample user already exists: {user_email}")

        # ── 4. Assign channels to admin (owner + moderator) ───────────────────
        for channel in channels_map.values():
            channel.owner = admin
            channel.moderator = admin
            channel.save(update_fields=["owner", "moderator"])

            ChannelMembership.objects.get_or_create(
                channel=channel, user=admin,
                defaults={"role": ChannelMembership.Role.OWNER, "can_post": True},
            )
            # Also add learner as member
            ChannelMembership.objects.get_or_create(
                channel=channel, user=learner,
                defaults={"role": ChannelMembership.Role.MEMBER, "can_post": True},
            )
            # Update member count
            count = ChannelMembership.objects.filter(channel=channel).count()
            Channel.objects.filter(pk=channel.pk).update(member_count=count)

        # ── 5. Seed discussions into MongoDB ──────────────────────────────────
        self.stdout.write("")
        disc_count = 0
        for ch_name, title, body in DISCUSSIONS:
            channel = channels_map.get(ch_name)
            if not channel:
                continue

            # Check if a discussion with this title already exists
            existing = list_discussions(channel.pk, limit=100)
            if any(d.get("title") == title for d in existing):
                self.stdout.write(f"  –  Discussion already exists: \"{title[:50]}\"")
                continue

            try:
                disc_id = create_discussion(
                    channel_id=channel.pk,
                    author_id=admin.pk,
                    title=title,
                    body=body,
                )
                disc_count += 1
                self.stdout.write(f"  ✔  Discussion: \"{title[:60]}\"")

                # Add a few sample replies to the first discussion of each channel
                if disc_count <= len(CHANNELS):
                    for i, reply_body in enumerate(SAMPLE_REPLIES[:3]):
                        author = learner if i % 2 == 0 else admin
                        create_message(
                            discussion_id=disc_id,
                            author_id=author.pk,
                            body=reply_body,
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠  Could not create discussion \"{title[:40]}\": {e}")
                )

        # ── 6. Summary ────────────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅  Seeding complete!\n"
            f"    Channels:    {len(channels_map)}\n"
            f"    Discussions: {disc_count}\n"
            f"\n"
            f"    Admin login:   admin@peerlearn.dev  /  admin123\n"
            f"    Learner login: learner@peerlearn.dev /  learner123\n"
            f"    URL:           http://localhost\n"
        ))
