# Builds the frontend and serves the static output with nginx.
# NOT build-tested here (no Docker daemon in this environment) - see
# BUILD_VERIFICATION.md. Reviewed by hand for correctness.
FROM node:20-slim AS build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
# The backend's real URL at runtime, baked in at build time (Vite env
# vars are compile-time, not runtime) - override with --build-arg for a
# non-default backend location.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
