# HireSense web app: Vite build served by nginx, which also forwards /api to the API container (same-site cookies).
# Build:  docker build -t hiresense-web frontend      (API_UPSTREAM defaults to the compose service "backend:8000")
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Optional: an API on another domain (then the backend needs COOKIE_SAMESITE=none). Empty = same-site /api.
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:1.27-alpine
ENV API_UPSTREAM=backend:8000
# nginx's image renders /etc/nginx/templates/*.template with the environment at start-up
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
