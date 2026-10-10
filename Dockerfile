# AgentForge backend image.
#
# Single-stage, single-service image: install the package, copy the
# project, run uvicorn. No multi-stage build, no separate worker image -
# this is a learning project's API server, not a production fleet.
#
# NOT independently build-tested in the environment this project was
# built in (no Docker daemon available there) - see BUILD_VERIFICATION.md
# for exactly what that means and how to verify it yourself.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching: this only re-runs
# when pyproject.toml changes, not on every source edit).
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Now the actual project.
COPY backend/ backend/
COPY sample_project/ sample_project/
COPY knowledge_base/ knowledge_base/

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
