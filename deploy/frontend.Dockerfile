FROM node:22-alpine AS build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
RUN npm run build
FROM caddy:2-alpine
COPY --from=build /build/dist /srv/aurum
COPY deploy/Caddyfile /etc/caddy/Caddyfile
