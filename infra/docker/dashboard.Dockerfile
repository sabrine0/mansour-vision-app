# syntax=docker/dockerfile:1.7
#
# The Next.js command center. Built as a standalone bundle so the runtime image
# carries neither node_modules nor the source tree.

ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /build
COPY package.json package-lock.json* ./
COPY apps/command-center/package.json apps/command-center/
RUN npm ci --workspaces --include-workspace-root

FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /build/node_modules ./node_modules
COPY --from=deps /build/apps/command-center/node_modules ./apps/command-center/node_modules
COPY package.json ./
COPY apps/command-center ./apps/command-center
RUN npm run build --workspace apps/command-center

FROM node:${NODE_VERSION}-alpine AS runtime
WORKDIR /srv

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN apk add --no-cache curl tini \
 && addgroup -S -g 1001 mansour \
 && adduser -S -u 1001 -G mansour mansour

# `output: "standalone"` emits a self-contained server plus only the node_modules
# it actually reaches. The image is a fraction of the size and its attack surface
# shrinks with it.
COPY --from=builder --chown=mansour:mansour /build/apps/command-center/.next/standalone ./
COPY --from=builder --chown=mansour:mansour /build/apps/command-center/.next/static ./apps/command-center/.next/static
COPY --from=builder --chown=mansour:mansour /build/apps/command-center/public ./apps/command-center/public

USER mansour:mansour
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://localhost:3000/api/healthz || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "apps/command-center/server.js"]
