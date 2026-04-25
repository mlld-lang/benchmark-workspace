# Bench image for remote runs on Namespace.
#
# Build context expects two repos checked out side-by-side:
#   <context>/clean/   → mlld-lang/benchmark-workspace
#   <context>/mlld/    → mlld-lang/mlld
#
# See .github/workflows/bench-image.yml for the canonical build.

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:/root/.opencode/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq xz-utils \
      build-essential python3 python3-pip python3-venv \
 && rm -rf /var/lib/apt/lists/*

# Node 22 (mlld build target)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y nodejs \
 && rm -rf /var/lib/apt/lists/*

# uv (Python package manager used by bench)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# opencode CLI (LLM harness)
RUN npm install -g opencode-ai

# nsc CLI — installed but not strictly required at runtime since the GH Actions
# workflow handles artifact upload. Keeping it available makes ad-hoc upload
# from inside the container possible.
RUN curl -fsSL https://get.namespace.so/install.sh | bash || \
    echo "WARN: nsc install failed; container can still run without it"

ARG MLLD_REF=main
ARG CLEAN_REF=main
ARG IMAGE_SHA=unknown
ENV IMAGE_SHA=${IMAGE_SHA}
ENV MLLD_REF=${MLLD_REF}
ENV CLEAN_REF=${CLEAN_REF}

# Build mlld runtime
COPY mlld /opt/mlld
WORKDIR /opt/mlld
RUN npm ci && npm run build && npm link

# Bench repo
COPY clean /workspace/clean
WORKDIR /workspace/clean

# bench/pyproject.toml resolves mlld-sdk via `../.mlld-sdk` (a local symlink
# pointing into the mlld checkout). Recreate it inside the image so uv sync
# can find the editable SDK.
RUN ln -sfn /opt/mlld/sdk/python /workspace/clean/.mlld-sdk

# Sync python deps into the bench project venv
RUN /root/.local/bin/uv sync --project bench

# Smoke check
RUN mlld --version && echo "node $(node --version)" && echo "uv $(/root/.local/bin/uv --version)"

# Entrypoint
COPY clean/bench/docker/entrypoint.sh /usr/local/bin/bench-entrypoint
RUN chmod +x /usr/local/bin/bench-entrypoint

WORKDIR /workspace/clean
CMD ["/usr/local/bin/bench-entrypoint"]
