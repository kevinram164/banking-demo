# Fix for Kong 404 Error

## Problem
Kong is returning 404 for `/api/auth/login` because it's configured to use database mode (`KONG_DATABASE: postgres`) but also has a declarative config file. In database mode, Kong ignores the declarative config, so routes aren't loaded.

## Solution

Update `docker-compose.yml` to use declarative config mode:

### 1. Remove Kong Database Service (lines 21-38)
Delete the entire `kong-db` service section.

### 2. Remove Kong Migrations Service (lines 52-66)
Delete the entire `kong-migrations` service section.

### 3. Update Kong Service (lines 68-108)
Replace the Kong service configuration with:

```yaml
  # Kong API Gateway (using declarative config mode - no database needed)
  kong:
    image: kong:3.4
    container_name: kong-gateway
    environment:
      KONG_DATABASE: "off"  # Use declarative config mode (no database)
      KONG_DECLARATIVE_CONFIG: /kong/kong.yml
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ERROR_LOG: /dev/stderr
      KONG_ADMIN_LISTEN: 0.0.0.0:8001
      KONG_PROXY_LISTEN: 0.0.0.0:8000
    ports:
      - "8000:8000"  # Proxy port
      - "8443:8443"  # Proxy SSL port
      - "8001:8001"  # Admin API
      - "8444:8444"  # Admin API SSL
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

### 4. Remove kongdata Volume (line 214)
Remove `kongdata:` from the volumes section.

## After Making Changes

1. **Stop and remove old containers:**
   ```bash
   docker compose down
   docker rm -f kong-db kong-migrations kong-gateway
   ```

2. **Rebuild and start:**
   ```bash
   docker compose up -d --build
   ```

3. **Verify Kong is working:**
   ```bash
   # Check Kong logs
   docker compose logs kong
   
   # Test the route
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"test","password":"test123"}'
   ```

## Key Changes

- `KONG_DATABASE: "off"` - Enables declarative config mode
- Removed `kong-db` service - Not needed for declarative mode
- Removed `kong-migrations` service - Not needed for declarative mode
- Removed `kongdata` volume - Not needed
- Removed `kong-migrations` dependency from Kong service

## Why This Works

When `KONG_DATABASE: "off"`, Kong reads routes directly from the `kong.yml` file instead of from a database. This is simpler for development and exactly what we need since we have a declarative config file.
