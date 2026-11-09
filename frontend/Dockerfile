# ===== Stage 1: Build React =====
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
RUN npm run build \
    && printf '%s\n' 'blue' > /app/build/variant.txt

# ===== Stage 2: Nginx (OpenShift-friendly) =====
FROM nginx:alpine

COPY nginx-main.conf /etc/nginx/nginx.conf
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

RUN chown -R nginx:0 /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+rwX /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+w /etc/nginx

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
