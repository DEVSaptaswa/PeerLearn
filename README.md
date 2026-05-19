# 🎓 PeerLearn — Peer Learning & Doubt Sharing Platform

> A production-grade, monolithic Django application for collaborative peer learning.  
> Combines Reddit-style threaded discussions with Discord-style presence and sidebar — all in a striking dark UI.

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Feature List](#2-feature-list)
3. [Technical Architecture](#3-technical-architecture)
4. [Project Structure](#4-project-structure)
5. [Database Schemas](#5-database-schemas)
6. [Prerequisites](#6-prerequisites)
7. [Quick Start (Docker)](#7-quick-start-docker)
8. [Environment Variables](#8-environment-variables)
9. [Running in Development Mode](#9-running-in-development-mode)
10. [Running in Production Mode](#10-running-in-production-mode)
11. [Makefile Commands](#11-makefile-commands)
12. [API Endpoint Reference](#12-api-endpoint-reference)
13. [How the Hybrid Database Works](#13-how-the-hybrid-database-works)
14. [Moderation System](#14-moderation-system)
15. [Real-Time Presence System](#15-real-time-presence-system)
16. [Adding HTTPS (Production)](#16-adding-https-production)
17. [Troubleshooting](#17-troubleshooting)

---

## 1. Project Overview

PeerLearn is a **strictly monolithic Django platform** where students and learners can:

- Organise into topic-based **Channels** (e.g. `#python`, `#linear-algebra`)
- Start **discussion threads** and reply in nested, timestamped conversations
- See **who is online right now** via a live presence sidebar
- **Moderate** communities with full audit trails and soft-deletion
- **Search** across users, channels, and message content simultaneously

The platform deliberately uses **three different databases** for three different jobs:

| Layer | Technology | Responsibility |
|---|---|---|
| Relational | **MySQL 8** | Users, profiles, friendships, channel membership, moderation logs |
| Document | **MongoDB 7** | Threaded discussions, messages, search analytics |
| Cache / KV | **Redis 7** | Real-time presence, session storage, application cache |

---

## 2. Feature List

### 👤 Accounts & Profiles
- Email-based registration and login
- Custom display names and bio
- Avatar upload with **automatic initial fallback** (coloured circle with first letter) if no image is set — colour is deterministically derived from the username
- Friend request system (send / accept / reject)
- Explicit status override: **Online**, **Do Not Disturb**, **Appear Offline**

### 📡 Real-Time Presence
- Every HTTP request from an authenticated user silently updates a Redis key
- Friend sidebar auto-polls every 30 seconds to refresh statuses
- Status boundaries:
  - 🟢 **Active** — seen within the last 5 minutes
  - 🟡 **Away** — seen 5–30 minutes ago
  - ⚫ **Offline** — seen more than 30 minutes ago or key expired
- Animated glowing border for online friends

### 📚 Channels & Threads
- Create channels with custom name, emoji icon, hex accent colour
- **Public channels** — anyone can join and post immediately
- **Private channels** — anyone can read threads, but posting requires moderator approval via the **Request Access** workflow
- Reddit-style upvoting on threads
- Nested reply threads inside discussions
- Invite friends directly from the right sidebar into any joined channel

### 🛡️ Moderation
- Each channel has a designated **Moderator** (defaults to creator)
- Moderators can soft-delete any **message** or entire **discussion thread**
- Deleted messages are **never physically removed** from MongoDB — the record is preserved and the frontend replaces the content with: *"This message was removed by the moderator for violating community guidelines."*
- Every action is written to an immutable **ModerationLog** row in MySQL
- Moderators see a live panel of pending access requests for private channels

### 🔍 Unified Search
- Single search bar queries **MySQL** (users, channels) and **MongoDB** (discussion titles, message bodies) simultaneously
- Results appear in a categorised dropdown with live debouncing (350 ms)
- All queries are logged to MongoDB's `search_logs` collection for analytics

### 🎨 UI/UX
- Full **dark theme** design system inspired by Discord + Reddit
- 3-column layout: left channel sidebar, main content pane, right friends sidebar
- Collapsible hamburger sidebar (state persisted in `localStorage`)
- Smooth page fade transitions on navigation
- Modal animations (scale-in) for compose, invite, and profile popups
- Fully responsive — sidebars collapse at 1100 px and 720 px breakpoints

---

## 3. Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP :80
┌──────────────────────▼──────────────────────────────────────┐
│                      Nginx 1.25                             │
│  • Serves /static/ and /media/ directly from volumes        │
│  • Proxies all other requests to Gunicorn                   │
│  • Gzip, security headers, client_max_body_size 10 MB       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP :8000 (internal)
┌──────────────────────▼──────────────────────────────────────┐
│             Django 4.2 + Gunicorn 21 (3 workers)            │
│                                                             │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  accounts  │  │   channels   │  │     discussions     │ │
│  │  (MySQL)   │  │   (MySQL)    │  │     (MongoDB)       │ │
│  └────────────┘  └──────────────┘  └─────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  core  (middleware · context_processors · home feed) │   │
│  └─────────────────────────────────────────────────────┘   │
└──────┬───────────────────┬───────────────────┬─────────────┘
       │                   │                   │
 ┌─────▼──────┐   ┌────────▼──────┐   ┌───────▼───────┐
 │  MySQL 8.0 │   │  MongoDB 7.0  │   │   Redis 7.2   │
 │            │   │               │   │               │
 │ Users      │   │ discussions   │   │ Presence keys │
 │ Profiles   │   │ messages      │   │ Sessions      │
 │ Friendships│   │ search_logs   │   │ Cache         │
 │ Channels   │   │               │   │               │
 │ Memberships│   │ Full-text idx │   │ TTL-based     │
 │ Mod logs   │   │ on title+body │   │ eviction      │
 └────────────┘   └───────────────┘   └───────────────┘
```

### Docker Service Map

```
peerlearn_nginx   ─► :80 (public)
peerlearn_web     ─► :8000 (internal, behind nginx)
peerlearn_mysql   ─► :3306 (internal only in prod, exposed in dev)
peerlearn_mongo   ─► :27017 (internal only in prod, exposed in dev)
peerlearn_redis   ─► :6379 (internal only in prod, exposed in dev)
```

All five services communicate on the Docker bridge network `peerlearn_network`.

---

## 4. Project Structure

```
peer_learning/
│
├── Dockerfile                  ← Multi-stage build (builder + runtime)
├── docker-compose.yml          ← Production 5-service stack
├── docker-compose.dev.yml      ← Dev overrides (hot-reload, exposed ports)
├── Makefile                    ← Convenience command aliases
├── requirements.txt
├── manage.py
├── .env                        ← Your secrets (not committed)
├── .env.example                ← Public template
├── .dockerignore
├── .gitignore
│
├── docker/
│   ├── entrypoint.sh           ← Waits for DBs → migrates → starts app
│   ├── mysql/
│   │   └── init.sql            ← MySQL first-boot initialization
│   └── mongo/
│       └── init.js             ← MongoDB user creation + index bootstrap
│
├── nginx/
│   └── nginx.conf              ← Reverse proxy + static file config
│
├── peer_learning/              ← Django project package
│   ├── settings.py             ← Unified config (MySQL + Mongo + Redis + Whitenoise)
│   ├── urls.py                 ← Root URL dispatcher
│   └── wsgi.py
│
├── apps/
│   ├── accounts/               ← AUTH layer (MySQL)
│   │   ├── models.py           ← User, Profile, Friendship
│   │   ├── views.py            ← Auth, profile, friend API, status API, search API
│   │   ├── forms.py
│   │   ├── signals.py          ← Auto-create Profile on User creation
│   │   ├── admin.py
│   │   ├── apps.py
│   │   └── urls.py
│   │
│   ├── channels/               ← COMMUNITY layer (MySQL)
│   │   ├── models.py           ← Channel, ChannelMembership, AccessRequest,
│   │   │                          ChannelInvite, ModerationLog
│   │   ├── views.py            ← CRUD, join/leave, access workflow, invite, mod
│   │   ├── forms.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   └── urls.py
│   │
│   ├── discussions/            ← CONTENT layer (MongoDB)
│   │   ├── views.py            ← Thread/message CRUD, upvote, soft-delete, search
│   │   ├── apps.py
│   │   └── urls.py
│   │
│   └── core/                   ← INFRASTRUCTURE layer
│       ├── views.py            ← Home feed aggregator
│       ├── middleware.py       ← UserPresenceMiddleware → Redis
│       ├── context_processors.py ← Sidebar data injected into all templates
│       ├── apps.py             ← Bootstraps MongoDB indexes on startup
│       ├── urls.py
│       └── management/
│           └── commands/
│               └── seed_data.py ← Dev seed command
│
├── utils/
│   ├── mongo_client.py         ← PyMongo singleton + all collection helpers
│   └── redis_client.py         ← Presence tracking + cache utilities
│
├── templates/
│   ├── base.html               ← 3-column master layout
│   ├── index.html              ← Home feed
│   ├── accounts/
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── profile.html
│   │   └── edit_profile.html
│   ├── channels/
│   │   ├── channel_list.html   ← Discover page
│   │   ├── channel_detail.html ← Thread list + compose modal + mod panel
│   │   └── create_channel.html
│   └── discussions/
│       └── discussion_detail.html ← Full thread + reply composer
│
└── static/
    ├── css/
    │   └── main.css            ← Complete design system (~1000 lines)
    └── js/
        └── main.js             ← All interactive behaviour (~1000 lines)
```

---

## 5. Database Schemas

### MySQL Tables

#### `auth_users`
| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| email | VARCHAR(254) UNIQUE | Login credential |
| username | VARCHAR(150) UNIQUE | Display handle |
| display_name | VARCHAR(60) | Optional friendly name |
| bio | TEXT | |
| password | VARCHAR(128) | Hashed (Django PBKDF2) |
| is_active / is_staff / is_superuser | BOOL | |

#### `user_profiles`
| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| user_id | FK → auth_users | OneToOne |
| avatar | VARCHAR | Upload path |
| avatar_color | CHAR(7) | Hex colour for initial fallback |
| threads_started | INT | Denormalised counter |
| joined_at | DATETIME | |

#### `friendships`
| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| from_user_id | FK → auth_users | |
| to_user_id | FK → auth_users | |
| status | ENUM(pending, accepted, blocked) | |
| created_at / updated_at | DATETIME | |

#### `channels`
| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| name | VARCHAR(80) UNIQUE | |
| slug | SLUG UNIQUE | URL-safe identifier |
| description | TEXT | |
| icon | VARCHAR(2) | Emoji |
| color | CHAR(7) | Hex accent |
| privacy | ENUM(public, private) | |
| owner_id | FK → auth_users | |
| moderator_id | FK → auth_users | |
| member_count | INT | Denormalised |

#### `channel_memberships`
| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| channel_id | FK → channels | |
| user_id | FK → auth_users | |
| role | ENUM(member, moderator, owner) | |
| can_post | BOOL | Key for private channel gating |
| joined_at | DATETIME | |

#### `access_requests`
| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| channel_id | FK | |
| user_id | FK | |
| message | TEXT | Optional applicant note |
| status | ENUM(pending, approved, denied) | |
| reviewed_by_id | FK nullable | |

#### `moderation_logs` (immutable audit trail)
| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| channel_id | FK | |
| moderator_id | FK | |
| action | ENUM(delete_message, delete_discussion, approve_access, ...) | |
| target_mongo_id | CHAR(24) | MongoDB ObjectId of affected document |
| target_user_id | FK nullable | |
| reason | TEXT | |
| created_at | DATETIME | |

### MongoDB Collections

#### `discussions`
```json
{
  "_id": ObjectId,
  "channel_id": 42,
  "author_id": 7,
  "title": "What's the best way to learn decorators?",
  "body": "I've been writing Python for 6 months...",
  "upvotes": 14,
  "reply_count": 8,
  "is_private_channel": false,
  "is_deleted": false,
  "created_at": ISODate,
  "updated_at": ISODate
}
```
**Indexes:** `channel_id ASC`, `(title TEXT, body TEXT)` full-text, `created_at DESC`

#### `messages`
```json
{
  "_id": ObjectId,
  "discussion_id": "507f1f77bcf86cd799439011",
  "author_id": 12,
  "body": "Great question! Here's how I think about it...",
  "parent_message_id": null,
  "upvotes": 3,
  "is_deleted": false,
  "deleted_by_moderator": false,
  "deleted_by": null,
  "deleted_at": null,
  "created_at": ISODate,
  "updated_at": ISODate
}
```
**Indexes:** `discussion_id ASC`, `body TEXT`, `author_id ASC`

#### `search_logs`
```json
{
  "_id": ObjectId,
  "query": "dynamic programming",
  "user_id": 5,
  "result_count": 12,
  "created_at": ISODate
}
```

### Redis Keys

| Key | Value | TTL | Purpose |
|---|---|---|---|
| `pl:presence:<uid>` | UNIX timestamp (float) | 1800 s | Last HTTP activity |
| `pl:status:<uid>` | `invisible` or `dnd` | 1800 s | Explicit status override |
| `pl:cache:<key>` | arbitrary string | configurable | Application cache |
| Django session keys | session data | 86400 s | User sessions |

---

## 6. Prerequisites

| Tool | Minimum Version | Check |
|---|---|---|
| **Docker** | 24.x | `docker --version` |
| **Docker Compose** | v2.x (plugin) | `docker compose version` |
| **GNU Make** | any | `make --version` |

> No Python, MySQL, MongoDB, or Redis installations are needed on the host machine — Docker provides them all.

---

## 7. Quick Start (Docker)

### Step 1 — Clone the repository

```bash
git clone https://github.com/yourname/peerlearn.git
cd peerlearn
```

### Step 2 — Configure environment

```bash
cp .env.example .env
```

For a quick local test the defaults in `.env` work as-is. For any real deployment, edit `.env` and set:

```bash
# Generate a real secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# Paste the output as DJANGO_SECRET_KEY in .env
```

### Step 3 — Build and start

```bash
# Build images and start all 5 services (production mode)
make up

# --- OR run directly with Docker Compose ---
docker compose up --build -d
```

The first boot will:
1. Pull base images (MySQL, MongoDB, Redis, Nginx, Python)
2. Build the Django application image
3. Wait for all databases to be ready
4. Run `python manage.py migrate` (creates all MySQL tables)
5. Run `python manage.py collectstatic`
6. Seed sample data — 7 channels, 7 discussions, admin user (`SEED_DATA=true` in `.env`)
7. Start Gunicorn with 3 worker processes

> ⏱ **First boot takes 60–120 seconds** — MySQL and MongoDB need time to initialize their data directories.

### Step 4 — Open the app

```
http://localhost
```

**Default admin credentials (seeded):**
```
Email:    admin@peerlearn.dev
Password: admin123
```

### Step 5 — Disable re-seeding

After the first successful boot, set `SEED_DATA=false` in `.env` to prevent the seed command from running again on every restart:

```bash
# Edit .env
SEED_DATA=false

# Restart just the web container
make restart
```

---

## 8. Environment Variables

All variables live in `.env`. The file is read by both `docker-compose.yml` and Django's `python-dotenv`.

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(placeholder)* | **Required in production.** Django signing key. |
| `DEBUG` | `False` | `True` enables Django debug mode and detailed error pages. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated list of valid hostnames. |
| `MYSQL_DB` | `peer_learning` | Database name. |
| `MYSQL_USER` | `peerlearn` | App DB user (least-privilege). |
| `MYSQL_PASSWORD` | `peerpassword` | App DB password. |
| `MYSQL_ROOT_PASSWORD` | `rootpassword` | MySQL root password (container only). |
| `MYSQL_HOST` | `mysql` | Docker service name — do not change unless using external MySQL. |
| `MYSQL_PORT` | `3306` | |
| `MONGO_URI` | `mongodb://peerlearn:...@mongo:27017/...` | Full connection string. |
| `MONGO_DB` | `peer_learning` | MongoDB database name. |
| `MONGO_ROOT_USER` | `admin` | MongoDB root user. |
| `MONGO_ROOT_PASSWORD` | `mongopassword` | MongoDB root password. |
| `MONGO_APP_PASSWORD` | `mongoapppwd` | Password for the `peerlearn` MongoDB app user. |
| `REDIS_HOST` | `redis` | Docker service name. |
| `REDIS_PORT` | `6379` | |
| `REDIS_DB` | `0` | Redis database index. |
| `REDIS_PASSWORD` | `redispassword` | Redis `requirepass` value. |
| `SEED_DATA` | `true` | Set to `false` after first boot. |
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

---

## 9. Running in Development Mode

Development mode replaces Gunicorn with Django's `runserver` (hot-reload) and exposes all database ports for local GUI tools.

```bash
make dev

# --- OR ---
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

In dev mode:
- Django app: **http://localhost:8000** (direct, bypasses nginx)
- MySQL: **localhost:3306**
- MongoDB: **localhost:27017**
- Redis: **localhost:6379**

Connect with your preferred GUI:
- MySQL Workbench / TablePlus → `localhost:3306`, user: `peerlearn`, password from `.env`
- MongoDB Compass → `mongodb://peerlearn:mongoapppwd@localhost:27017/peer_learning?authSource=peer_learning`
- RedisInsight / Another Redis Desktop Manager → `localhost:6379`, password from `.env`

To make code changes visible immediately the `apps/`, `templates/`, and `static/` directories are bind-mounted into the container — save a file in your editor and Django restarts automatically.

---

## 10. Running in Production Mode

```bash
# Start all services detached
make up

# Watch logs
make logs

# Check health
make health
```

**What runs in production:**
- **Nginx** terminates HTTP on port 80, serves `/static/` and `/media/` from volumes
- **Gunicorn** runs with 3 sync workers (tune via the `CMD` in `Dockerfile`)
- **Whitenoise** acts as a secondary static file middleware (backup if Nginx is bypassed)
- All DB ports are unexposed to the host

**Worker tuning formula:**
```
workers = (2 × CPU cores) + 1
```
Edit the `CMD` in `Dockerfile` to adjust `--workers`.

---

## 11. Makefile Commands

| Command | Description |
|---|---|
| `make build` | Rebuild all images from scratch (no cache) |
| `make up` | Start all services in detached production mode |
| `make dev` | Start with development overrides (hot-reload, exposed ports) |
| `make down` | Stop all services |
| `make logs` | Stream logs from all services |
| `make logs-web` | Stream logs from the Django container only |
| `make logs-db` | Stream logs from MySQL, MongoDB, and Redis |
| `make shell` | Open a bash shell inside the `web` container |
| `make migrate` | Run `python manage.py migrate` inside the container |
| `make seed` | Run `python manage.py seed_data` to repopulate sample data |
| `make superuser` | Interactively create a Django superuser |
| `make collectstatic` | Re-collect static files |
| `make restart` | Restart only the `web` container (fast code deploy) |
| `make ps` | Show container status |
| `make health` | Show containers with ports and health status |
| `make clean` | Stop containers and remove networks (volumes kept) |
| `make nuke` | ⚠ Destroy everything: containers, volumes, images |

---

## 12. API Endpoint Reference

All endpoints require authentication unless stated otherwise.

### Core
| Method | URL | Description |
|---|---|---|
| `GET` | `/` | Home feed — threads from joined channels |

### Accounts
| Method | URL | Description |
|---|---|---|
| `GET/POST` | `/accounts/login/` | Login page |
| `GET/POST` | `/accounts/register/` | Registration page |
| `GET` | `/accounts/logout/` | Log out |
| `GET` | `/accounts/profile/` | Own profile |
| `GET` | `/accounts/profile/<username>/` | Public profile |
| `GET/POST` | `/accounts/profile/edit/` | Edit own profile |
| `POST` | `/accounts/friend/request/<user_id>/` | Send friend request |
| `POST` | `/accounts/friend/respond/<friendship_id>/` | Accept or reject request |
| `POST` | `/accounts/status/set/` | Set presence override `{"status": "invisible"}` |
| `GET` | `/accounts/api/friends/status/` | Friend list + live statuses (JSON) |
| `GET` | `/accounts/api/users/search/?q=` | User search (JSON) |
| `GET` | `/accounts/api/profile-mini/<user_id>/` | Lightweight profile for friend modal |

### Channels
| Method | URL | Description |
|---|---|---|
| `GET` | `/channels/` | Discover all channels |
| `GET/POST` | `/channels/create/` | Create a channel |
| `GET` | `/channels/<slug>/` | Channel detail — thread list |
| `POST` | `/channels/<slug>/join/` | Join channel |
| `POST` | `/channels/<slug>/leave/` | Leave channel |
| `POST` | `/channels/<slug>/request-access/` | Request posting rights (private channels) |
| `POST` | `/channels/<slug>/invite/` | Invite a friend `{"user_id": 42}` |
| `POST` | `/channels/<slug>/mod/delete-discussion/` | Moderator: soft-delete a thread |
| `POST` | `/channels/access-request/<id>/review/` | Moderator: approve/deny access request |
| `GET` | `/channels/api/search/?q=` | Channel search (JSON) |

### Discussions
| Method | URL | Description |
|---|---|---|
| `GET` | `/discussions/search/?q=` | **Unified search** across MySQL + MongoDB |
| `GET` | `/discussions/<channel_slug>/` | Thread list (JSON, paginated) |
| `POST` | `/discussions/<channel_slug>/create/` | Create a new thread |
| `GET` | `/discussions/<channel_slug>/<discussion_id>/` | Thread detail page |
| `POST` | `/discussions/<channel_slug>/<discussion_id>/reply/` | Post a message |
| `POST` | `/discussions/upvote/<discussion_id>/` | Upvote a thread |
| `POST` | `/discussions/mod/<channel_slug>/message/<message_id>/delete/` | Moderator: soft-delete message |

---

## 13. How the Hybrid Database Works

### When a user posts a message

```
Browser
  │  POST /discussions/python/abc123/reply/
  │  {"body": "Here's my approach..."}
  ▼
Django view (discussions/views.py)
  │
  ├─► MySQL: verify ChannelMembership (is user allowed to post?)
  │
  ├─► MongoDB: insert into messages collection
  │     {discussion_id, author_id, body, created_at, is_deleted: false}
  │
  ├─► MongoDB: $inc reply_count on parent discussion document
  │
  └─► JSON response → browser appends message card to DOM
```

### When a moderator deletes a message

```
Browser
  │  POST /discussions/mod/python/message/xyz789/delete/
  ▼
Django view
  │
  ├─► MySQL: verify ChannelMembership.role == moderator
  │
  ├─► MongoDB: update messages
  │     {$set: {is_deleted: true, deleted_by_moderator: true, deleted_by: <mod_id>}}
  │     ← record is NEVER removed
  │
  ├─► MySQL: INSERT into moderation_logs
  │     (channel, moderator, action='delete_message', target_mongo_id='xyz789')
  │
  └─► JSON: {deleted: true, placeholder: "🚫 This message was removed..."}
            → browser replaces message body in DOM (no page reload)
```

### Unified search flow

```
GET /discussions/search/?q=dynamic+programming
  │
  ├─► MySQL: SELECT users WHERE username ILIKE '%..%'
  ├─► MySQL: SELECT channels WHERE name ILIKE '%..%'
  ├─► MongoDB: $text search on discussions (title + body indexes)
  ├─► MongoDB: $text search on messages (body index)
  ├─► MongoDB: INSERT into search_logs (analytics)
  └─► Combined JSON response → rendered in search dropdown
```

---

## 14. Moderation System

The moderation system is designed around two hard constraints:

**1. Nothing is ever physically deleted from MongoDB.**

`moderator_soft_delete_message()` in `utils/mongo_client.py` only sets:
```python
{"is_deleted": True, "deleted_by_moderator": True, "deleted_by": moderator_id, "deleted_at": now}
```

The message body remains intact in the database for compliance, appeals, and analytics.

**2. Every moderation action is immutable.**

`ModerationLog` in MySQL has no `UPDATE`/`DELETE` permissions in normal application code. Each action creates a new row — the log is append-only and never altered.

**Frontend behaviour:**
- When `_serialize_message()` encounters `deleted_by_moderator == True`, it substitutes the placeholder text before sending JSON to the browser
- The `modDeleteMessage()` JS function replaces the DOM content immediately without a page reload, for a seamless UX

---

## 15. Real-Time Presence System

### How it works

```
User makes any HTTP request (page load, AJAX, form submit)
  │
  ▼
UserPresenceMiddleware (apps/core/middleware.py)
  │
  └─► utils/redis_client.py :: update_presence(user_id)
        └─► REDIS SET pl:presence:<uid> <unix_timestamp> EX 1800
```

```
Friend sidebar JS (main.js)
  │
  └─► Every 30 seconds: GET /accounts/api/friends/status/
        │
        └─► Django view
              └─► get_bulk_statuses(friend_ids)
                    └─► Redis PIPELINE (2 GETs per user, single round-trip)
                          ├─► GET pl:status:<uid>   (override check)
                          └─► GET pl:presence:<uid> (last-seen timestamp)
                                │
                                └─► Resolve: active / away / offline
                                      └─► JSON → JS updates DOM rings
```

### Status resolution priority

```python
if override == "invisible":        return "offline"
if presence_key missing:           return "offline"
if elapsed <= 300:   # 5 min      return "active"
if elapsed <= 1800:  # 30 min     return "away"
else:                              return "offline"
```

Redis key TTL is 1800 s — if a user closes their browser and stops making requests, the key auto-expires and they fall to **offline** automatically with no cleanup job required.

---

## 16. Adding HTTPS (Production)

To add TLS with Let's Encrypt using Certbot:

```bash
# Install certbot on the host (or use the certbot Docker image)
docker compose exec nginx sh -c "apk add certbot certbot-nginx"

# Obtain certificate (replace with your domain)
docker compose exec nginx certbot --nginx -d yourdomain.com

# Auto-renewal
echo "0 0 * * * docker compose exec nginx certbot renew --quiet" | crontab -
```

Then update `nginx/nginx.conf`:
- Change `listen 80` to `listen 443 ssl`
- Add `ssl_certificate` and `ssl_certificate_key` directives
- Add a second server block to redirect HTTP → HTTPS

Also update `.env`:
```
ALLOWED_HOSTS=yourdomain.com
DEBUG=False
```

---

## 17. Troubleshooting

### `web` container exits immediately on first boot

**Cause:** MySQL hasn't finished initializing before the entrypoint tries to connect.  
**Fix:** The entrypoint already waits up to 90 s with `nc` polling. If MySQL is still slow:
```bash
# Check MySQL logs
make logs-db

# Increase the sleep in docker/entrypoint.sh (line: "sleep 3" → "sleep 8")
```

### `django.db.utils.OperationalError: (2002, "Can't connect to server")`

The `MYSQL_HOST` in `.env` must match the Docker Compose service name exactly (`mysql`), not `localhost`.

### MongoDB authentication fails

The `MONGO_URI` in `.env` uses the **app user** (`peerlearn`), not `root`. This user is created by `docker/mongo/init.js` on first boot. If you changed `MONGO_APP_PASSWORD` after the initial volume was created, destroy the volume and recreate:
```bash
docker compose down
docker volume rm peer_learning_mongo_data
make up
```

### Static files return 404

Run collectstatic manually:
```bash
make collectstatic
```

### "address already in use" on port 80

Another process is using port 80. Stop it or change the port in `docker-compose.yml`:
```yaml
ports:
  - "8080:80"   # use localhost:8080 instead
```

### Resetting everything and starting fresh

```bash
make nuke    # destroys containers, volumes, images
make up      # rebuilds from scratch (re-seeds data)
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run in dev mode: `make dev`
4. Make changes — Django hot-reloads automatically
5. Run tests: `docker compose exec web python manage.py test`
6. Open a Pull Request

## License

MIT © PeerLearn Contributors
