FROM --platform=linux/amd64 python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY ugecy ./ugecy
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "ugecy.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "600"]
