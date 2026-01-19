# Fix for Backend psycopg2 Error

## Problem
The old `banking-backend` container is trying to use `psycopg2` but the package installed is `psycopg` (version 3).

## Solution

### Step 1: Stop and Remove Old Containers
```bash
docker compose down
docker rm -f banking-backend  # Remove old backend container if it exists
```

### Step 2: Rebuild Services
```bash
docker compose up -d --build
```

## What Was Fixed

1. **Updated `common/db.py`** - Now converts `postgresql://` to `postgresql+psycopg://` to explicitly use psycopg3
2. **Updated `backend/db.py`** - Same fix for the old backend service (if you still want to use it)

## Note

The old `backend` service is no longer in `docker-compose.yml` since we've moved to microservices. If you see errors from `banking-backend`, it's an old container that needs to be removed.

## Verify

After rebuilding, check that only microservices are running:
```bash
docker compose ps
```

You should see:
- auth-service
- account-service
- transfer-service
- notification-service
- kong-gateway
- frontend
- postgres
- redis

No `banking-backend` should be listed.
