# ===== Stage 1: Build React =====
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files trước để cache npm install
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build React
RUN npm run build

# ===== Stage 2: Serve bằng Nginx =====
FROM nginx:alpine

# Xóa config mặc định (optional)
RUN rm /etc/nginx/conf.d/default.conf

# Copy build output
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
