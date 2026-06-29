FROM node:24-alpine AS builder

WORKDIR /app

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
