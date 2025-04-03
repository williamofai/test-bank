# Test Bank - A Test Architect’s Demo
Clone repo from `https://github.com/williaofai/test-bank`.

A complex banking app built to showcase system design, testability, and practical skills. Initially deployed on a Digital Ocean droplet (`144.126.239.47:5000`) with Flask and SQLite, now upgraded to FastAPI, Redis, and PostgreSQL on an Ubuntu VM (2 vCPUs, 2GB RAM).

## Features (Updated)
- **REST API:** Endpoints for login, transfers, account management (`/transfer`, `/check`, etc.).
- **Async Processing:** Redis queue with 6 workers for transfers.
- **Load Tested:** 5000 transfers at 100% success (36.98 req/s).
- **DB:** PostgreSQL (`test_bank`) with 33,111 accounts.

## Tech Stack (Updated)
- FastAPI (Python)
- Redis (queue)
- PostgreSQL (`test_bank`)
- Ubuntu VM (2 vCPUs, 2GB RAM)

## Latest Results (April 03, 2025)
- **Config**: FastAPI, 6 Redis workers, PostgreSQL (shared_buffers=512MB), 33,111 accounts @ £1M each.
- **5000 Transfers**: 100% success (5000/5000), 0.127s latency, 36.98 req/s, 0 failures.
- **Key Fixes**: Resolved "string indices" error, seeded £1M balances to eliminate "Insufficient funds".

## Setup
```bash
pip install -r requirements.txt
systemctl start redis-server
systemctl start postgresql
systemctl start banking-app.service  # Uvicorn service
for i in {1..6}; do python3 redis_worker.py & done
./load_test_transfer.py
