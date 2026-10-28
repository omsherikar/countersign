FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /uvx /bin/

# Dependencies live in /opt/venv, outside /app, because compose bind-mounts
# ./services/api over /app for hot reload.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .

EXPOSE 8000
# Keep idle connections open longer than the web proxy reuses them (uvicorn's default
# is 5 s, which the Next.js proxy outlives and reports as "socket hang up").
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "75"]
