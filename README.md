# Subscription Monolith

Back-end monolith built with **FastAPI** and **Python 3.12+** for managing personal service subscriptions and sending expiration reminders.

---

## Table of Contents

- [About the Project](#about-the-project)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Infrastructure](#infrastructure)
- [Authentication and Security](#authentication-and-security)
- [Current Status](#current-status)
- [Environment Variables](#environment-variables)
- [Getting Started](#getting-started)
- [API Documentation](#api-documentation)
- [License](#license)

---

## About the Project

Most people today pay for multiple subscription services -- streaming platforms, cloud storage, music apps, software licenses, gym memberships -- and it is easy to lose track of when each one renews. Many of these services charge automatically, and by the time you notice, the payment has already gone through for something you may no longer use.

**Subscription Monolith** solves this problem. It is a platform where users can register all of their active subscriptions in one place, with their respective renewal dates and costs. As a renewal date approaches, the system sends an email reminder so the user can make an informed decision: renew and pay, or cancel before being charged.

### How it works

1. The user creates an account (via email/password or Google login).
2. They register their active subscriptions, including the service name, cost, billing cycle, and next renewal date.
3. A scheduled worker monitors upcoming renewal dates and, when one is approaching, publishes a message to RabbitMQ.
4. An email worker consumes that message and sends a reminder to the user via SMTP.
5. The user receives the reminder and decides whether to keep or cancel the subscription.

### Architecture decisions

The project follows a modular monolith architecture. Each domain (auth, users, subscriptions) is isolated into its own route, service, and schema layer while sharing a single deployment unit and database. This keeps the codebase simple to deploy and operate while maintaining clear boundaries for future extraction into independent services if needed.

- **Async-first I/O** across all external service connections (database, cache, message broker).
- **Clear separation of concerns** through dedicated layers for routing, business logic, data validation, and infrastructure.
- **Message-driven background processing** via RabbitMQ workers for email delivery and scheduled tasks, keeping API response times fast.

---

## Tech Stack

| Layer             | Technology                              |
| ----------------- | --------------------------------------- |
| Framework         | FastAPI + Uvicorn                       |
| Language          | Python 3.12+                            |
| Database          | PostgreSQL (via asyncpg)                |
| Cache             | Redis (via redis-py async)              |
| Message Broker    | RabbitMQ (via aio-pika)                 |
| Authentication    | JWT (PyJWT) + bcrypt + Google OAuth2    |
| Data Validation   | Pydantic v2                             |
| Configuration     | pydantic-settings (env-based)           |
| Email             | SMTP (worker-based delivery)            |

---

## Project Structure

```
subscription-monolith/
|-- main.py                     # Application entrypoint and lifespan management
|-- requirements.txt            # Python dependencies
|-- .env                        # Environment variables (not versioned)
|
|-- core/                       # Infrastructure and cross-cutting concerns
|   |-- config/config.py        # Centralized settings via pydantic-settings
|   |-- postgresql/postgresql.py# Async connection pool (asyncpg)
|   |-- redis/redis.py          # Async Redis client wrapper
|   |-- rabbitmq/rabbitmq.py    # Async RabbitMQ connection (aio-pika)
|   |-- security/security.py    # JWT, bcrypt, Google OAuth2, role-based access
|   |-- logger/logger.py        # Structured logging configuration
|
|-- routes/                     # HTTP route definitions (controllers)
|   |-- auth/router.py          # Login and Google OAuth endpoints
|   |-- users/router.py         # User management endpoints
|   |-- subscription/router.py  # Subscription management endpoints
|
|-- services/                   # Business logic layer
|   |-- auth/auth_service.py    # Authentication logic (credentials + Google)
|   |-- user/user_service.py    # User CRUD operations
|   |-- subscription/           # Subscription business logic
|   |-- cache/cache_service.py  # Redis get/set/delete operations
|   |-- messaging/messaging_service.py  # RabbitMQ message publishing
|
|-- schemas/                    # Pydantic models for request/response validation
|   |-- auth.py                 # Login request models
|   |-- user.py                 # User request/response models
|   |-- subscription.py         # Subscription models
|
|-- workers/                    # Background workers (message consumers)
|   |-- smtp/email_worker.py    # Email delivery worker
|   |-- schedule/               # Scheduled tasks
|
|-- templates/                  # Email templates
|   |-- email.py                # HTML email template definitions
|
|-- functions/                  # Shared utilities
    |-- utils/utils.py          # Response helpers, data serialization
```

---

## Infrastructure

All external service connections are managed through dedicated modules inside `core/` and share a consistent lifecycle pattern: they initialize on application startup and close gracefully on shutdown, controlled by FastAPI's `lifespan` context manager.

### PostgreSQL

Async connection pool via `asyncpg`. Connections are injected into route handlers through FastAPI's dependency injection system (`Depends`). The pool is configured with a minimum of 1 and maximum of 3 connections.

### Redis

Async client via `redis-py`. Used as the caching layer through a generic key-value service (`cache_service.py`) that supports JSON serialization, TTL-based expiration, and on-demand invalidation.

### RabbitMQ

Async connection via `aio-pika` with persistent message delivery (delivery mode 2). Used to decouple the API layer from long-running tasks such as email sending. Messages are published to queues via `messaging_service.py` and consumed by dedicated workers.

### SMTP

Configured for transactional email delivery via an SMTP relay. The architecture separates email dispatch into a background worker (`workers/smtp/`) that consumes messages from RabbitMQ, keeping the API response times fast.

---

## Authentication and Security

The security module (`core/security/security.py`) provides:

- **Password hashing** with bcrypt (salt generation included).
- **JWT access tokens** with configurable expiration (HS256 algorithm by default).
- **Google OAuth2** token verification for social login, with automatic user provisioning on first login.
- **Cookie-based session management** using HttpOnly, Secure, SameSite=Lax cookies.
- **Role-based access control** with a rank hierarchy (BASIC, ADMIN) and configurable minimum-rank middleware.
- **Password reset flow** with a multi-step token validation process (email verification code, then password update).

---

## Current Status

The table below summarizes the implementation progress of each module:

| Module                | Status         | Notes                                                  |
| --------------------- | -------------- | ------------------------------------------------------ |
| Core Infrastructure   | Complete       | PostgreSQL, Redis, RabbitMQ, Config, Logger             |
| Security              | Complete       | JWT, bcrypt, Google OAuth2, role-based access           |
| Auth Routes           | Complete       | Login (credentials), Login (Google)                     |
| Auth Service          | Complete       | Credential validation, Google token verification        |
| User Service          | Complete       | User creation and retrieval                             |
| Cache Service         | Complete       | Generic key-value operations with TTL                   |
| Messaging Service     | Complete       | RabbitMQ message publishing                             |
| Utility Functions     | Complete       | Response wrappers, data serialization helpers            |
| Subscription Routes   | Scaffolded     | File structure created, implementation pending           |
| Subscription Service  | Scaffolded     | File structure created, implementation pending           |
| User Routes           | Scaffolded     | File structure created, implementation pending           |
| Email Worker          | Scaffolded     | File structure created, implementation pending           |
| Email Templates       | Scaffolded     | File structure created, implementation pending           |
| Scheduled Workers     | Scaffolded     | File structure created, implementation pending           |

---

## Environment Variables

Create a `.env` file at the project root with the following variables:

```env
# Application
ENVIRONMENT=development
API_PORT=8000

# PostgreSQL
DB_HOST=
DB_PORT=5432
DB_USER=
DB_PASSWORD=
DB_NAME=

# RabbitMQ
RABBITMQ_HOST=
RABBITMQ_PORT=5672
RABBITMQ_USER=
RABBITMQ_PASSWORD=

# Redis
REDIS_HOST=
REDIS_PORT=6379
REDIS_PASSWORD=

# JWT
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# SMTP
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=

# Google OAuth
GOOGLE_CLIENT_ID=
```

---

## Getting Started

### Prerequisites

- Python 3.12 or later
- PostgreSQL instance
- Redis instance
- RabbitMQ instance

### Installation

```bash
# Clone the repository
git clone https://github.com/pablozr/subscription-monolith.git
cd subscription-monolith

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your service credentials
```

### Running

```bash
# Development server
uvicorn main:app --host 0.0.0.0 --port 5685 --reload
```

---

## API Documentation

Once the server is running, interactive API documentation is available at:

- **Swagger UI**: `http://localhost:5685/api/v1/subreminders/docs`

---

## License

This project is private and not licensed for public distribution.
