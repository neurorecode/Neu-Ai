# Build the React app, then serve it (and proxy /api) with Caddy
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
# Caddyfile is mounted by docker-compose (deploy/Caddyfile)
