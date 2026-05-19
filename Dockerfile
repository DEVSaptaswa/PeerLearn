# ═══════════════════════════════════════════════════════════════════════════════
# PeerLearn — Dockerfile
# Multi-stage build:
#   stage 1 (builder) → compile C extensions (mysqlclient, Pillow)
#   stage 2 (runtime) → lean final image, no compilers
# ═══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        pkg-config \
        default-libmysqlclient-dev \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="PeerLearn <dev@peerlearn.dev>"
LABEL description="Peer Learning & Doubt Sharing Platform"

# Runtime-only system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
        # mysqlclient runtime
        default-libmysqlclient-dev \
        # Pillow runtime
        libjpeg62-turbo \
        zlib1g \
        libpng16-16 \
        # Health checks & service waiting
        curl \
        netcat-openbsd \
        # Python MySQL client needs this at runtime
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --gid 1001 peerlearn \
 && useradd  --uid 1001 --gid peerlearn --shell /bin/bash --create-home peerlearn

# Install pre-built wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
 && rm -rf /wheels

# App directory
WORKDIR /app
RUN mkdir -p /app/staticfiles /app/media \
 && chown -R peerlearn:peerlearn /app

# Copy source
COPY --chown=peerlearn:peerlearn . /app/

# Copy entrypoint
COPY --chown=peerlearn:peerlearn docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER peerlearn

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", \
     "peer_learning.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--worker-class", "sync", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
