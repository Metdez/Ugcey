FROM --platform=linux/amd64 python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
# Optional build secret "ca": only needed when building behind a TLS-intercepting proxy.
# It is mounted for this step only and never written into the image.
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export SSL_CERT_FILE=/run/secrets/ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY ugecy ./ugecy
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "ugecy.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "600"]
