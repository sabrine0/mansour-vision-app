# syntax=docker/dockerfile:1.7
#
# One image definition for every Python service. `SERVICE` selects which.
#
# Four services with four near-identical Dockerfiles is four places to forget a
# security fix. The build arg costs one line and removes the drift.
#
# Build from the repository root:
#   docker build -f infra/docker/python-service.Dockerfile --build-arg SERVICE=core-api .

ARG PYTHON_VERSION=3.11

# ---------------------------------------------------------------------------
# Builder: resolve and install dependencies into an isolated virtualenv.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ARG SERVICE
ARG SERVICE_PACKAGE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# build-essential is needed for any sdist that lacks a wheel. It stays in the
# builder stage and never reaches the runtime image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy only the package manifests first so that a source-only change does not
# invalidate the dependency layer.
COPY packages/py-common/pyproject.toml   packages/py-common/
COPY packages/contracts/pyproject.toml   packages/contracts/
COPY services/${SERVICE}/pyproject.toml  services/${SERVICE}/

COPY packages/py-common   packages/py-common
COPY packages/contracts   packages/contracts
COPY services/${SERVICE}  services/${SERVICE}

RUN pip install --upgrade pip setuptools wheel \
 && pip install ./packages/py-common ./packages/contracts "./services/${SERVICE}"

# Fail the build if an AGPL/GPL/SSPL dependency has entered the image (ADR 0002).
# `ultralytics` must never appear here, at any version, for any reason. This gate
# is what makes the licensing posture enforceable rather than aspirational.
RUN pip install pip-licenses \
 && pip-licenses --format=json --with-authors --with-urls > /opt/licenses.json \
 && pip-licenses --fail-on="GNU Affero General Public License v3;GNU General Public License v3 (GPLv3);GNU General Public License v2 (GPLv2);Server Side Public License (SSPL)" \
 && pip uninstall -y pip-licenses prettytable wcwidth

# ---------------------------------------------------------------------------
# Runtime: no compiler, no source tree, no root.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG SERVICE
ARG SERVICE_PACKAGE
ARG GIT_SHA=unknown

LABEL org.opencontainers.image.title="mansour-${SERVICE}" \
      org.opencontainers.image.vendor="Tomorrow Systems" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      com.mansour.privacy="anonymous operational monitoring only; see docs/adr/0004"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH"

# curl is the healthcheck. tini reaps zombies and forwards SIGTERM to PID 1,
# without which the graceful drain in mansour_common.lifecycle never runs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 mansour \
 && useradd --system --uid 1001 --gid mansour --no-create-home mansour

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/licenses.json /opt/licenses.json

USER mansour:mansour
WORKDIR /srv

ENV SERVICE_MODULE=${SERVICE_PACKAGE}
EXPOSE 8000 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD curl --fail --silent http://localhost:${HEALTH_PORT:-8080}/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "exec python -m ${SERVICE_MODULE}.main"]
