# frontend-green — FE version mới (blue-green lab)
# Context: banking-demo/frontend-green
# Image: harbor-platform.../banking-demo/frontend-green:<tag>
#
# Không build từ folder frontend/ với ARG — tránh lẫn UI_VARIANT.

FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
RUN npm run build \
    && printf '%s\n' 'GREEN v2' > /app/build/variant.txt \
    && sed -i 's/<title>Banking Demo<\/title>/<title>NPD Banking (Green)<\/title>/' /app/build/index.html \
    && sed -i 's/<div id="root"><\/div>/<div id="root"><\/div><!-- GREEN v2 -->/' /app/build/index.html

FROM nginx:alpine

COPY nginx-main.conf /etc/nginx/nginx.conf
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

RUN chown -R nginx:0 /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+rwX /etc/nginx/conf.d /usr/share/nginx/html \
    && chmod -R g+w /etc/nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
