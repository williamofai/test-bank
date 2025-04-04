# Test Bank - A Test Architect’s Demo

Clone the repo from `https://github.com/williaofai/test-bank`.

A complex banking app built to showcase system design, testability, and practical skills. Initially deployed on a Digital Ocean droplet (`144.126.239.47:5000`) with Flask and SQLite, now upgraded to FastAPI, Redis, and PostgreSQL on an Ubuntu VM (1 vCPU, 1GB RAM) and accessible at `https://speytech.com` with SSL.

## Features (Updated)
- **REST API:** Endpoints for login, transfers, account management, and more (`/transfer`, `/check`, `/open_account`, `/list`, `/api`, `/api/balance/{account_number}`, `/api/history/{account_number}`, `/withdraw`, `/register`).
- **UI Endpoints:** Interactive web interface for users (`/`, `/login`, `/logout`, `/dashboard`, `/check-balance`, `/view-history`, `/balance/{account_number}`, `/history/{account_number}`, `/deposit`).
- **Async Processing:** Redis queue for transfer jobs (processed immediately in the current implementation).
- **Load Tested:** 
  - Account Creation: 1,710 accounts/sec, 100% success (10,000/10,000 accounts), 0.029s effective avg latency per batch, 4.289s max batch latency.
  - Transfers: 41.87 transfers/sec, 100% success (5,000/5,000 transfers), 0.195s avg total latency, 0 failures.
- **Database:** PostgreSQL (`test_bank`) with 10,000+ accounts seeded at £1M each.
- **Security:** Deployed with Let’s Encrypt SSL, HTTP redirects to HTTPS.

## Tech Stack (Updated)
- **FastAPI (Python)**: High-performance web framework for API and UI endpoints.
- **Redis**: Queue for transfer jobs.
- **PostgreSQL (`test_bank`)**: Database with `accounts` and `transfer_jobs` tables.
- **Nginx**: Reverse proxy for HTTPS traffic.
- **Ubuntu VM**: 1 vCPU, 1GB RAM on Digital Ocean, accessible at `https://speytech.com`.

## Latest Results (April 04, 2025)
- **Config**: FastAPI, Redis, PostgreSQL (shared_buffers=512MB), 10,000+ accounts @ £1M each.
- **Account Creation (10,000 Accounts)**: 100% success (10,000/10,000), 1,710 accounts/sec, 0.029s effective avg latency per batch, 4.289s max individual batch latency.
- **Transfers (5,000 Transfers)**: 100% success (5,000/5,000), 41.87 req/s, 0.195s avg total latency, 0 failures.
- **Key Fixes**: Resolved 400 "Bad Request" error in transfer test, seeded £1M balances to eliminate "Insufficient funds" errors.

## Setup
To run the Test Bank app locally or on a server:

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis and PostgreSQL services
systemctl start redis-server
systemctl start postgresql

# Start the FastAPI application
systemctl start banking-app.service  # Uvicorn service

# Run load tests
./load_test_open_account.py  # Test account creation
./load_test_transfer.py      # Test transfers
