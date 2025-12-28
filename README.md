Banking Demo Application – Overview
1. Introduction

This project is a Banking Demo Application designed to demonstrate a modern web architecture using a stateless backend, session management with Redis, relational data storage with PostgreSQL, and real-time notifications via WebSocket.
The application focuses on core banking features rather than UI complexity, making it suitable for:
- technical interviews
- system design discussions
- DevOps / backend / platform engineering training

2. Key Features

- User registration and login
- Session-based authentication (stored in Redis)
- Account balance management
- Money transfer between users
- Real-time transfer notifications using WebSocket
- Designed to run in Docker and easily migrate to Kubernetes

3. High-Level Architecture:
```
+-------------+        HTTP / WebSocket        +------------------+
|   Frontend  |  <--------------------------> |    Backend API   |
|  (React)    |                                |   (FastAPI)      |
+-------------+                                +------------------+
        |                                              |
        |                                              |
        |                     Redis                    |
        |          +--------------------------------+  |
        |          |  Session Store / Cache         |  |
        |          |  (User session, online state)  |  |
        |          +--------------------------------+  |
        |                                              |
        |                 PostgreSQL                   |
        |          +--------------------------------+  |
        |          |  Users, Balances, Transfers     | |
        |          |  Transaction history            | |
        |          +--------------------------------+  |
```

4. Component Breakdown
4.1 Frontend (React)

- Provides UI for login, balance viewing, transfers, and notifications
- Communicates with backend via REST APIs
- Maintains session ID (issued by backend) in browser storage
- Opens a persistent WebSocket connection for real-time notifications

4.2 Backend API (FastAPI)
Implements REST endpoints:

- /login, /register
- /me, /balance
- /transfer
Stateless by design
All authentication state is stored in Redis
Handles WebSocket connections for push notifications

4.3 Redis (Session & Realtime Support)

Redis is used for:

- Storing user sessions (session ID → user mapping)
- Tracking online users
- Supporting real-time notification delivery
- Enabling horizontal scalability (future-ready for Redis Pub/Sub)
- This allows backend pods to remain stateless, which is ideal for scaling in Kubernetes.

4.4 PostgreSQL (Persistent Storage)

PostgreSQL is the system of record for:

- User accounts
- Account balances
- Transfer transactions
- Notification history
All critical financial data is persisted in PostgreSQL to ensure consistency and durability.
