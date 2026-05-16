# Bench image for remote runs on Namespace.
#
# Build context expects three repos checked out side-by-side:
#   <context>/clean/      → mlld-lang/benchmark-workspace
#   <context>/mlld/       → mlld-lang/mlld
#   <context>/opencode/   → adamavenir/opencode (mlld fork w/ MCP reconnect fix)
#
# AgentDojo is installed from PyPI (pinned in bench/pyproject.toml).
# The forked runner/grading code now lives at clean/src/agentdojo_*.py.
#
# See .github/workflows/bench-image.yml for the canonical build.

ARG MLLD_PREBUILT_TAG=policy-redesign
FROM ghcr.io/mlld-lang/mlld-prebuilt:${MLLD_PREBUILT_TAG} AS mlld-src

FROM ubuntu:24.04
ARG MLLD_PREBUILT_TAG

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/bin:/opt/opencode-bin/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq xz-utils unzip \
      build-essential python3 python3-pip python3-venv \
 && rm -rf /var/lib/apt/lists/*

# Node 22 (mlld build target)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y nodejs \
 && rm -rf /var/lib/apt/lists/*

# uv (Python package manager used by bench)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# opencode CLI — pre-built binary from ghcr.io/mlld-lang/opencode-prebuilt:dev.
# Built once via .github/workflows/opencode-prebuild.yml; re-run that workflow
# when adamavenir/opencode#dev changes. Pinning to :dev moves with the
# prebuild; pin to :sha-<...> for reproducibility.
#
# This was previously a from-source build via bun (~80s build + ~few-minute
# layer push). Pre-building once dropped both: bench-image now skips the
# opencode build step entirely, and the binary layer is shared across
# rebuilds in GHCR (push-if-changed semantics).
COPY --from=ghcr.io/mlld-lang/opencode-prebuilt:dev /opt/opencode-bin /opt/opencode-bin
RUN ln -sf /opt/opencode-bin/bin/opencode /usr/local/bin/opencode

# nsc CLI — installed but not strictly required at runtime since the GH Actions
# workflow handles artifact upload. Keeping it available makes ad-hoc upload
# from inside the container possible.
RUN curl -fsSL https://get.namespace.so/install.sh | bash || \
    echo "WARN: nsc install failed; container can still run without it"

ARG MLLD_REF=main
ARG MLLD_SHA=unknown
ARG CLEAN_REF=main
ARG IMAGE_SHA=unknown
ENV IMAGE_SHA=${IMAGE_SHA}
ENV MLLD_REF=${MLLD_REF}
ENV MLLD_SHA=${MLLD_SHA}
ENV CLEAN_REF=${CLEAN_REF}

# Labels are inspectable via `docker inspect` — bench-run.yml uses these
# to detect if the image's baked mlld is stale relative to upstream.
# opencode.sha lives on the ghcr.io/.../opencode-prebuilt:dev image and is
# inspectable separately if needed.
LABEL mlld.ref="${MLLD_REF}"
LABEL mlld.sha="${MLLD_SHA}"
LABEL clean.sha="${CLEAN_REF}"

# mlld runtime — pre-built tree from ghcr.io/mlld-lang/mlld-prebuilt:<ref>.
# Built by .github/workflows/mlld-prebuild.yml; that workflow self-skips
# when the requested ref's HEAD SHA already matches the baked image's
# mlld.sha label. Re-run the workflow to refresh.
#
# We still run `npm link` here to wire /usr/local/bin/mlld → the package's
# bin entry. Cheap (just symlinks); doesn't rebuild anything.
COPY --from=mlld-src /opt/mlld /opt/mlld
WORKDIR /opt/mlld
RUN npm link

# Bench repo (AgentDojo comes from PyPI via uv sync below)
COPY clean /workspace/clean
WORKDIR /workspace/clean

# bench/pyproject.toml resolves mlld-sdk via `../.mlld-sdk` (a local symlink
# pointing into the mlld checkout). Recreate it inside the image so uv sync
# can find the editable SDK.
RUN ln -sfn /opt/mlld/sdk/python /workspace/clean/.mlld-sdk

# Sync python deps into the bench project venv
RUN /root/.local/bin/uv sync --project bench

# Smoke check
RUN mlld --version \
 && echo "node $(node --version)" \
 && echo "uv $(/root/.local/bin/uv --version)" \
 && echo "opencode $(opencode --version 2>/dev/null || echo unknown)"

# Entrypoint
COPY clean/bench/docker/entrypoint.sh /usr/local/bin/bench-entrypoint
RUN chmod +x /usr/local/bin/bench-entrypoint

WORKDIR /workspace/clean
CMD ["/usr/local/bin/bench-entrypoint"]
