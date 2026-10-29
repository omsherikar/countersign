# openmined.psi ships wheels for linux x86_64 and macOS arm64 only, so this image is always
# built for linux/amd64 (emulated on Apple Silicon).
FROM --platform=linux/amd64 python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /bin/

# The venv lives outside /app so a bind mount of ./services/psi keeps it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --group test && rm -rf /root/.cache

COPY . .

# PSI_ROLE picks the side: "partner" (the other regulator's registry) or "client"
# (Countersign's PSI client, called only by the api).
ENV PSI_ROLE=partner
EXPOSE 8002
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8002"]
