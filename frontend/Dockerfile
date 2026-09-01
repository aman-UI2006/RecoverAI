# Multi-stage production build for RecoverAI Frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (enables Docker layer caching)
COPY frontend/package*.json ./
RUN npm ci

# Copy source code and build production assets
COPY frontend/ ./
RUN npm run build

# Stage 2: Serve compiled static assets via Nginx
FROM nginx:alpine AS runner

# Copy compiled dist from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
