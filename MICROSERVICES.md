# Microservices Architecture with Kong API Gateway

## Architecture Overview

This banking application has been refactored into a microservices architecture using Kong API Gateway.

```
┌─────────────┐
│   Frontend  │
│   (React)   │
└──────┬──────┘
       │
       │ HTTP/WebSocket
       ▼
┌─────────────────────────────────┐
│      Kong API Gateway            │
│      (Port 8000)                 │
└──────┬──────────────────────────┘
       │
       ├───► Auth Service (8001)
       ├───► Account Service (8002)
       ├───► Transfer Service (8003)
       └───► Notification Service (8004)
```

## Microservices

### 1. Auth Service (Port 8001)
- **Endpoints:**
  - `POST /register` - User registration
  - `POST /login` - User login and session creation
  - `GET /health` - Health check

- **Responsibilities:**
  - User authentication
  - Session management (Redis)
  - Password hashing

### 2. Account Service (Port 8002)
- **Endpoints:**
  - `GET /me` - Get current user profile and balance
  - `GET /balance` - Get current user balance
  - `GET /health` - Health check

- **Responsibilities:**
  - User profile management
  - Balance queries

### 3. Transfer Service (Port 8003)
- **Endpoints:**
  - `POST /transfer` - Transfer money between users
  - `GET /health` - Health check

- **Responsibilities:**
  - Money transfers
  - Balance updates (with database locks)
  - Transaction recording
  - Notification triggering

### 4. Notification Service (Port 8004)
- **Endpoints:**
  - `GET /notifications` - Get user notifications
  - `WebSocket /ws` - Real-time notifications
  - `GET /health` - Health check

- **Responsibilities:**
  - Notification storage
  - Real-time notifications via WebSocket
  - User presence tracking

## Kong API Gateway Routes

All services are accessed through Kong at port 8000:

- `/api/auth/register` → Auth Service `/register`
- `/api/auth/login` → Auth Service `/login`
- `/api/account/me` → Account Service `/me`
- `/api/account/balance` → Account Service `/balance`
- `/api/transfer/transfer` → Transfer Service `/transfer`
- `/api/notifications/notifications` → Notification Service `/notifications`
- `/ws` → Notification Service `/ws` (WebSocket)

## Shared Common Library

All microservices share a common library located in `/common`:

- `common/db.py` - Database connection and session management
- `common/models.py` - SQLAlchemy models (User, Transfer, Notification)
- `common/redis_utils.py` - Redis utilities (sessions, presence, notifications)
- `common/auth.py` - Password hashing utilities

## Running the Application

1. **Start all services:**
   ```bash
   docker compose up -d --build
   ```

2. **Check service status:**
   ```bash
   docker compose ps
   ```

3. **View logs:**
   ```bash
   docker compose logs -f [service-name]
   ```

4. **Access the application:**
   - Frontend: http://localhost:3000
   - Kong Admin API: http://localhost:8001
   - Kong Proxy: http://localhost:8000

## Kong Admin API

Kong Admin API is available at port 8001. You can use it to:

- View services: `curl http://localhost:8001/services`
- View routes: `curl http://localhost:8001/routes`
- View plugins: `curl http://localhost:8001/plugins`

## Database Schema

All services share the same PostgreSQL database:
- **Database:** banking
- **Tables:** users, transfers, notifications

## Redis Usage

Redis is used for:
- Session storage (`session:{session_id}` → `user_id`)
- User presence tracking (`presence:{user_id}`)
- Pub/Sub for real-time notifications (`notify:{user_id}`)

## Health Checks

All services have health check endpoints at `/health` that verify:
- Database connectivity
- Redis connectivity
- Service status

## Development Notes

- Services are built from the root context to access the `/common` directory
- Each service has its own Dockerfile that copies the common library
- Kong uses declarative configuration from `kong/kong.yml`
- Frontend nginx proxies all `/api/*` and `/ws` requests to Kong
