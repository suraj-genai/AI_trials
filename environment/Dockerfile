# === BEGIN realm base (do not edit) ===
FROM --platform=linux/amd64 ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates curl git patch ripgrep fd-find jq \
        python3 python3-pytest \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/fdfind /usr/local/bin/fd

RUN mkdir -p /app /logs/verifier
# === END realm base ===


# --- task-specific dependencies ---
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
 && rm -rf /var/lib/apt/lists/*


# --- task files ---
COPY data/allocator.c /app/allocator.c
COPY data/allocator.h /app/allocator.h
COPY data/metadata.c /app/metadata.c
COPY data/metadata.h /app/metadata.h

# --- writable workspace ---
RUN useradd -m -s /bin/bash agent \
 && mkdir -p /app/output /app/solution \
 && chown agent:agent /app /app/output /app/solution \
 && chown -R agent:agent /app/*.c /app/*.h