FROM --platform=$BUILDPLATFORM node:24-alpine AS builder

WORKDIR /app/frontend
ENV NEXT_TELEMETRY_DISABLED=1

COPY frontend/package*.json ./
RUN npm ci

COPY VERSION /app/VERSION
COPY CHANGELOG.md /app/CHANGELOG.md
COPY scripts/changelog.mjs /app/scripts/changelog.mjs
COPY frontend/app ./app
COPY frontend/public ./public
COPY frontend/next.config.mjs frontend/eslint.config.mjs ./
RUN npm run build

FROM caddy:2-alpine

COPY frontend/Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/frontend/out /srv/frontend

EXPOSE 80
