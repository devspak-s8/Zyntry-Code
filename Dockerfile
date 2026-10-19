# Zyntry Code execution worker — a reproducible "durable computer" for a VPS.
#
# Runs the execworker (git + fs + command tools) against your Zyntry backend.
# Resource limits (CPU/memory rlimits) are enforced by the kernel for every
# command the worker runs.

FROM python:3.13-slim

# git is required for workspace checkout/branch isolation/diffs.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY execworker ./execworker

RUN pip install --no-cache-dir .

# Workspace checkouts live here; mount a volume to persist them.
ENV ZYNTRY_WORKSPACES_DIR=/workspaces

ENV ZYNTRY_CPU_LIMIT_SECONDS=120 \
    ZYNTRY_MEM_LIMIT_MB=1024

ENTRYPOINT ["python", "-m", "execworker.main"]
CMD ["--backend", "http://host.docker.internal:8787"]