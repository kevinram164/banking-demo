# Microservices Setup Guide

## Quick Start

1. **Update docker-compose.yml** - Remove Kong database dependencies and use declarative config mode:
   - Remove `kong-db` service
   - Remove `kong-migrations` service  
   - Set `KONG_DATABASE: "off"` in Kong service
   - Remove `kongdata` volume

2. **Build and start:**
   ```bash
   docker compose up -d --build
   ```

3. **Verify services:**
   ```bash
   docker compose ps
   curl http://localhost:8000/api/auth/login
   ```

## Architecture

- **Kong Gateway**: Port 8000 (proxy), 8001 (admin)
- **Auth Service**: Port 8001 (internal)
- **Account Service**: Port 8002 (internal)
- **Transfer Service**: Port 8003 (internal)
- **Notification Service**: Port 8004 (internal)

## API Routes through Kong

- `POST /api/auth/register` → Auth Service
- `POST /api/auth/login` → Auth Service
- `GET /api/account/me` → Account Service
- `GET /api/account/balance` → Account Service
- `POST /api/transfer/transfer` → Transfer Service
- `GET /api/notifications/notifications` → Notification Service
- `WS /ws` → Notification Service (WebSocket)

## Manual docker-compose.yml Fix

If the file wasn't updated automatically, manually change Kong service to:

```yaml
kong:
  image: kong:3.4
  container_name: kong-gateway
  environment:
    KONG_DATABASE: "off"
    KONG_DECLARATIVE_CONFIG: /kong/kong.yml
    KONG_PROXY_ACCESS_LOG: /dev/stdout
    KONG_ADMIN_ACCESS_LOG: /dev/stdout
    KONG_PROXY_ERROR_LOG: /dev/stderr
    KONG_ADMIN_ERROR_LOG: /dev/stderr
    KONG_ADMIN_LISTEN: 0.0.0.0:8001
    KONG_PROXY_LISTEN: 0.0.0.0:8000
  ports:
    - "8000:8000"
    - "8443:8443"
    - "8001:8001"
    - "8444:8444"
  volumes:
    - ./kong/kong.yml:/kong/kong.yml:ro
  depends_on:
    auth-service:
      condition: service_started
    account-service:
      condition: service_started
    transfer-service:
      condition: service_started
    notification-service:
      condition: service_started
  healthcheck:
    test: ["CMD", "kong", "health"]
    interval: 10s
    timeout: 10s
    retries: 10
    start_period: 30s
  restart: unless-stopped
```

And remove `kong-db` and `kong-migrations` services, and `kongdata` volume.
