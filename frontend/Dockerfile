# ===== Stage 1: Build React =====
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ===== Stage 2: Nginx (OpenShift-friendly) =====
FROM nginx:alpine

COPY nginx-main.conf /etc/nginx/nginx.conf
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

# conf.d có thể bị entrypoint thử ghi (ipv6 script) — group 0 writable
RUN chown -R nginx:0 /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+rwX /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+w /etc/nginx

# Non-root: listen 8080 (Helm service.targetPort: 8080)
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
