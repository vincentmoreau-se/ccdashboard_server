# syntax=docker/dockerfile:1

# ---- Stage 1: build the Vite SPA -------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /fe

# Install deps first (cached unless lockfile changes)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build with the subpath base + API base baked in
COPY frontend/ ./
ARG VITE_BASE=/ccdash/
ARG VITE_API_BASE=/ccdash
ENV VITE_BASE=$VITE_BASE \
    VITE_API_BASE=$VITE_API_BASE
RUN npm run build
# -> /fe/dist

# ---- Stage 2: Python backend (serves API + the built SPA) ------------------
# NOTE: bullseye (glibc 2.31) on purpose. The host runs Docker 19.03 whose
# default seccomp profile blocks the clone3 syscall; newer glibc (bookworm)
# uses clone3 for thread creation and fails with "can't start new thread".
FROM python:3.11-slim-bullseye AS runtime
WORKDIR /app

# uv for dependency install (matches the repo's uv.lock)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install locked dependencies (no project package: pyproject has package=false)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code
COPY backend/app ./app

# Built frontend from stage 1
COPY --from=frontend /fe/dist ./frontend/dist

# Defaults (overridable via .env / compose); data dir is a mounted volume
ENV CCSRV_FRONTEND_DIST=/app/frontend/dist \
    CCSRV_DB_PATH=/data/ccsrv.db

EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
