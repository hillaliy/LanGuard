FROM --platform=$BUILDPLATFORM node:24-alpine AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package*.json ./
RUN npm ci

COPY app ./app
COPY public ./public
COPY next.config.mjs eslint.config.mjs ./
RUN npm run build

FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/out /srv/frontend

EXPOSE 80
