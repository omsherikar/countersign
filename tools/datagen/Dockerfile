FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    RULES_PATH=/app/rules.yaml

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# compose supplies the entrypoint (`datagen`); running the image alone prints usage.
CMD ["datagen", "--help"]
