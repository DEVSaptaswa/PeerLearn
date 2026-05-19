# ═══════════════════════════════════════════════════════════════════════════════
# PeerLearn — Makefile
# Convenience wrappers for common Docker Compose commands.
# Usage: make <target>
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: help build up down dev logs shell migrate seed restart clean nuke

# Default target
help:
	@echo ""
	@echo "  PeerLearn — Available Commands"
	@echo "  ──────────────────────────────────────────────────────"
	@echo "  make build      Build / rebuild all Docker images"
	@echo "  make up         Start all services in detached mode (production)"
	@echo "  make dev        Start in development mode (hot-reload, exposed ports)"
	@echo "  make down       Stop all services"
	@echo "  make logs       Tail logs for all services"
	@echo "  make shell      Open a bash shell inside the web container"
	@echo "  make migrate    Run Django database migrations"
	@echo "  make seed       Seed sample data (channels, admin user, threads)"
	@echo "  make restart    Restart the web service only"
	@echo "  make clean      Remove containers, networks (keep volumes)"
	@echo "  make nuke       ⚠ Destroy everything including volumes & images"
	@echo "  make superuser  Create a Django superuser interactively"
	@echo ""

# ── Build ──────────────────────────────────────────────────────────────────────
build:
	docker compose build --no-cache

# ── Production: start detached ─────────────────────────────────────────────────
up:
	docker compose up -d
	@echo "✅  PeerLearn running at http://localhost"

# ── Development: hot-reload + exposed DB ports ────────────────────────────────
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# ── Stop ──────────────────────────────────────────────────────────────────────
down:
	docker compose down

# ── Logs ──────────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f --tail=100

logs-web:
	docker compose logs -f --tail=100 web

logs-db:
	docker compose logs -f --tail=50 mysql mongo redis

# ── Shell ─────────────────────────────────────────────────────────────────────
shell:
	docker compose exec web bash

# ── Django management ─────────────────────────────────────────────────────────
migrate:
	docker compose exec web python manage.py migrate

seed:
	docker compose exec web python manage.py seed_data

superuser:
	docker compose exec web python manage.py createsuperuser

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

# ── Service management ────────────────────────────────────────────────────────
restart:
	docker compose restart web

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	docker compose down --remove-orphans

nuke:
	@echo "⚠  This will delete ALL containers, volumes, and images for this project."
	@read -p "   Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 0
	docker compose down -v --remove-orphans --rmi all
	@echo "🗑  Everything removed."

# ── Status ────────────────────────────────────────────────────────────────────
ps:
	docker compose ps

health:
	@echo "Checking service health..."
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
