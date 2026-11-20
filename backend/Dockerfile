# The deployed service. Built from the repository root (see backend/cloudbuild.yaml), because it
# needs the prompt and the settings file that live beside backend/.
#
# It installs the base dependencies only: no development tools and not the `live` group, so the
# model's library is not in the image, and no model key is ever set on the service.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.4 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-default-groups --no-install-project

COPY backend/src ./src
COPY backend/fixtures ./fixtures
COPY prompts /app/prompts
COPY evals/settings.toml /app/evals/settings.toml
RUN uv sync --frozen --no-default-groups

# Not root.
RUN useradd --system --no-create-home service
USER service

# Cloud Run sets PORT.
CMD ["sh", "-c", "exec /app/backend/.venv/bin/uvicorn domain_health.serve:app --host 0.0.0.0 --port ${PORT:-8080}"]
