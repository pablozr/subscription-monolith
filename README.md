# Subscription Monolith

Back-end monolith built with **FastAPI** and **Python 3.12+** for managing personal service subscriptions and sending expiration reminders.

---

## Table of Contents

- [About the Project](#about-the-project)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Infrastructure](#infrastructure)
- [Authentication and Security](#authentication-and-security)
- [API Routes](#api-routes)
- [Workers](#workers)
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
4. The email worker consumes that message and sends reminders to the user via SMTP.
5. The user receives the reminder and decides whether to keep or cancel the subscription.

### Architecture decisions

The project follows a modular monolith architecture. Each domain (auth, users, subscriptions, payment history) is isolated into its own route, service, and schema layer while sharing a single deployment unit and database. This keeps the codebase simple to deploy and operate while maintaining clear boundaries for future extraction into independent services if needed.

- **Async-first I/O** across all external service connections (database, cache, message broker).
- **Clear separation of concerns** through dedicated layers for routing, business logic, data validation, and infrastructure.
- **Message-driven background processing** via RabbitMQ workers for email delivery and scheduled tasks, keeping API response times fast.
- **No ORM** -- all database access uses raw parameterized SQL through asyncpg for full control and performance.

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
| Notifications     | SMTP worker                             |

---

## Project Structure

```
subscription-monolith/
|-- main.py                          # Application entrypoint and lifespan management
|-- requirements.txt                 # Python dependencies
|-- .env.example                     # Environment variables template
|-- manual_db_changes.sql            # Manual SQL updates (no migration framework)
|
|-- core/                            # Infrastructure and cross-cutting concerns
|   |-- config/config.py             # Centralized settings via pydantic-settings
|   |-- postgresql/postgresql.py     # Async connection pool singleton (asyncpg)
|   |-- redis/redis.py              # Async Redis client singleton
|   |-- rabbitmq/rabbitmq.py        # Async RabbitMQ connection singleton (aio-pika)
|   |-- security/security.py        # JWT, bcrypt, Google OAuth2, role-based access
|   |-- logger/logger.py            # Structured logging configuration
|
|-- routes/                          # HTTP route definitions
|   |-- auth/router.py              # Login, Google login, logout, password reset flow
|   |-- users/router.py             # User profile (GET /me, PUT /me, POST)
|   |-- subscription/router.py      # Subscription CRUD + cancel
|   |-- payment_history/router.py   # Register/list subscription payments
|
|-- services/                        # Business logic layer
|   |-- auth/auth_service.py        # Authentication logic (credentials + Google)
|   |-- user/user_service.py        # User CRUD operations
|   |-- subscription/subscription_service.py  # Subscription CRUD operations
|   |-- payment_history/payment_history_service.py # Payment registration and history
|   |-- cache/cache_service.py      # Redis get/set/delete with JSON serialization
|   |-- messaging/messaging_service.py  # RabbitMQ message publishing
|
|-- schemas/                         # Pydantic models for request/response validation
|   |-- auth.py                     # Login, forgot password, validate code, update password
|   |-- user.py                     # User create, update, response types
|   |-- subscription.py             # Subscription create, update, response types
|
|-- workers/                         # Background workers (standalone processes)
|   |-- smtp/email_worker.py        # RabbitMQ consumer for email delivery via SMTP
|   |-- schedule/renewal_reminder.py # Scheduled renewal reminder checker
|
|-- templates/                       # Email templates
|   |-- email.py                    # HTML email templates with placeholder tokens
|
|-- functions/                       # Shared utilities
    |-- utils/utils.py              # Response wrappers, data serialization helpers
```

Every module folder contains an `__init__.py` file.

---

## Infrastructure

All external service connections are managed through singleton classes inside `core/` and share a consistent lifecycle pattern: they initialize on application startup and close gracefully on shutdown, controlled by FastAPI's `lifespan` context manager.

### PostgreSQL

Async connection pool via `asyncpg`. Connections are injected into route handlers through FastAPI's dependency injection (`Depends`). The pool is configured with a minimum of 1 and maximum of 3 connections. All queries use raw parameterized SQL with positional placeholders (`$1, $2, $3`).

### Redis

Async client via `redis-py`. Used as the caching layer through a generic key-value service (`cache_service.py`) that supports JSON serialization, TTL-based expiration, and on-demand invalidation. Currently used for storing temporary password reset codes.

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

### Password Reset Flow

A complete multi-step flow using Redis for temporary codes and two-phase JWT tokens:

1. `POST /auth/forget-password` -- generates a 6-digit code, stores it in Redis (TTL 600s), publishes an email message via RabbitMQ, and returns a JWT with `canUpdate: false` in an `auth_reset` cookie.
2. `POST /auth/validate-code` -- validates the code against Redis. If correct, clears the Redis key and returns a new JWT with `canUpdate: true`.
3. `POST /auth/update-password` -- requires the `canUpdate: true` token. Updates the password and clears the `auth_reset` cookie.

---

## API Routes

### Auth (`/auth`)

| Method | Endpoint             | Auth     | Description                                  |
| ------ | -------------------- | -------- | -------------------------------------------- |
| POST   | `/login`             | Public   | Login with email and password                |
| POST   | `/google/login`      | Public   | Login with Google OAuth2 token               |
| POST   | `/logout`            | Required | Logout and clear auth cookie                 |
| POST   | `/forget-password`   | Public   | Request password reset code via email        |
| POST   | `/validate-code`     | Reset    | Validate the 6-digit reset code              |
| POST   | `/update-password`   | Reset    | Set new password (requires validated code)   |

### Users (`/users`)

| Method | Endpoint | Auth     | Description                          |
| ------ | -------- | -------- | ------------------------------------ |
| GET    | `/me`    | Required | Get authenticated user profile       |
| PUT    | `/me`    | Required | Update email and/or fullname         |
| POST   | `/`      | Public   | Create a new user                    |

### Subscriptions (`/subscriptions`)

| Method | Endpoint              | Auth     | Description                              |
| ------ | --------------------- | -------- | ---------------------------------------- |
| GET    | `/`                   | Required | List all subscriptions for the user      |
| GET    | `/{id}`               | Required | Get a specific subscription              |
| POST   | `/`                   | Required | Create a new subscription                |
| PUT    | `/{id}`               | Required | Update subscription fields               |
| PATCH  | `/{id}/cancel`        | Required | Cancel a subscription (sets CANCELED)    |
| DELETE | `/{id}`               | Required | Permanently delete a subscription        |

### Payments (`/payments`)

| Method | Endpoint                         | Auth     | Description                                         |
| ------ | -------------------------------- | -------- | --------------------------------------------------- |
| POST   | `/subscriptions/{subscriptionId}` | Required | Register a payment and advance `next_payment_date`   |
| GET    | `/subscriptions/{subscriptionId}` | Required | List payment history for one subscription            |
| GET    | `/history`                        | Required | List full user payment history with optional filters |

All user-owned data queries enforce IDOR protection via `AND user_id = $X`.

---

## Workers

Workers run as **standalone processes**, separate from the FastAPI application. They reuse the singleton classes from `core/` for their own connections.

### Email Worker

Consumes messages from the `email-queue` RabbitMQ queue and sends emails via SMTP. Supports HTML content and base64 attachments.

```bash
python -m workers.smtp.email_worker
```

### Renewal Reminder

Scheduled job that queries active subscriptions approaching their next payment date (based on `reminder_days_before`) and publishes reminder emails to the `email-queue`.

```bash
python -m workers.schedule.renewal_reminder
```

---

## Environment Variables

Create a `.env` file at the project root. Use `.env.example` as a template:

```bash
cp .env.example .env
```

| Variable                     | Description                          | Default       |
| ---------------------------- | ------------------------------------ | ------------- |
| `ENVIRONMENT`                | Runtime environment                  | `development` |
| `API_PORT`                   | Server port                          | `8000`        |
| `CORS_ALLOW_ORIGINS`         | Allowed CORS origins (comma-separated) | `http://localhost:4200` |
| `DB_HOST`                    | PostgreSQL host                      | --            |
| `DB_PORT`                    | PostgreSQL port                      | `5432`        |
| `DB_USER`                    | PostgreSQL user                      | --            |
| `DB_PASSWORD`                | PostgreSQL password                  | --            |
| `DB_NAME`                    | PostgreSQL database name             | --            |
| `RABBITMQ_HOST`              | RabbitMQ host                        | --            |
| `RABBITMQ_PORT`              | RabbitMQ port                        | `5672`        |
| `RABBITMQ_USER`              | RabbitMQ user                        | --            |
| `RABBITMQ_PASSWORD`          | RabbitMQ password                    | --            |
| `EMAIL_QUEUE_NAME`           | RabbitMQ queue for email worker      | `email-queue` |
| `REDIS_HOST`                 | Redis host                           | --            |
| `REDIS_PORT`                 | Redis port                           | `6379`        |
| `REDIS_PASSWORD`             | Redis password                       | `""`          |
| `SECRET_KEY`                 | JWT signing key                      | --            |
| `ALGORITHM`                  | JWT algorithm                        | `HS256`       |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Token expiration in minutes          | `1440`        |
| `RATE_LIMIT_WINDOW_SECONDS`  | Rate limit window in seconds         | `60`          |
| `RATE_LIMIT_LOGIN_MAX_REQUESTS` | Max requests for `/auth/login` per window | `5`     |
| `RATE_LIMIT_GOOGLE_LOGIN_MAX_REQUESTS` | Max requests for `/auth/google/login` per window | `10` |
| `RATE_LIMIT_FORGET_PASSWORD_MAX_REQUESTS` | Max requests for `/auth/forget-password` per window | `5` |
| `RATE_LIMIT_VALIDATE_CODE_MAX_REQUESTS` | Max requests for `/auth/validate-code` per window | `10` |
| `SMTP_HOST`                  | SMTP server host                     | --            |
| `SMTP_PORT`                  | SMTP server port                     | `587`         |
| `SMTP_USER`                  | SMTP login user                      | --            |
| `SMTP_PASSWORD`              | SMTP login password                  | --            |
| `EMAIL_FROM`                 | Sender email address                 | --            |
| `SMTP_TIMEOUT_SECONDS`       | SMTP timeout in seconds              | `15`          |
| `SMTP_USE_STARTTLS`          | Enables SMTP STARTTLS                | `true`        |
| `GOOGLE_CLIENT_ID`           | Google OAuth2 client ID              | --            |

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

# Apply manual database updates for payment history
psql -d subscription_db -f manual_db_changes.sql
```

### Running the API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Running the Workers

In separate terminal sessions:

```bash
# Email delivery worker
python -m workers.smtp.email_worker

# Renewal reminder (run on a schedule via cron or task scheduler)
python -m workers.schedule.renewal_reminder
```

---

## API Documentation

Once the server is running, interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/api/v1/subreminders/docs`

---

## License

This project is private and not licensed for public distribution.
