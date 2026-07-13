# ===== Stage 1: Build React =====
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ===== Stage 2: Nginx (OpenShift-friendly) =====
FROM nginx:alpine

# main config: pid/cache/temp → thư mục ghi được bởi UID bất kỳ (OCP)
COPY nginx-main.conf /etc/nginx/nginx.conf
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/build /usr/share/nginx/html

# OCP: process chạy UID trong dải namespace, group 0 — cần g+rwX
RUN mkdir -p /var/cache/nginx/client_temp \
             /var/cache/nginx/proxy_temp \
             /var/cache/nginx/fastcgi_temp \
             /var/cache/nginx/uwsgi_temp \
             /var/cache/nginx/scgi_temp \
             /var/run/nginx \
             /var/log/nginx \
    && chown -R nginx:0 /var/cache/nginx /var/run/nginx /var/log/nginx \
                       /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+rwX /var/cache/nginx /var/run/nginx /var/log/nginx \
                      /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+w /etc/nginx

# Non-root không bind :80 — listen 8080 (Service targetPort phải khớp)
EXPOSE 8080

# Không USER cố định — OCP gán UID trong dải namespace (group 0 + g+rwX ở trên)
CMD ["nginx", "-g", "daemon off;"]
