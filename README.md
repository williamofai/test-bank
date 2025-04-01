# Test Bank - A Test Architect’s Demo
...
Clone repo from `https://github.com/williamofai/test-bank`.

A complex banking app built to showcase system design, testability, and practical skills. Deployed on a Digital Ocean droplet (`144.126.239.47:5000`), this project features a REST API, stubbed external services, and a polished UI.

## Features
- **Account Lookup:** Check balances via HTML or API (`/api/balance/<account>`).
- **Deposits/Withdrawals:** With a fraud check stub (rejects >£1000, 1s delay).
- **Transaction History:** View via UI or API (`/api/history/<account>`).
- **Mock Login:** Fake user auth with SQLite `users` table.
- **Testability:** Stubs, logging-ready, and load-tested (100 requests in 0.87s).
- **UI:** Basic CSS for clean tables and success/error messages.

## Tech Stack
- Flask (Python)
- SQLite (`bank.db`)
- Digital Ocean droplet (Ubuntu)

## Why It Rocks for Testing
- **Stubs:** Fraud check simulates external dependencies—test latency or failures.
- **API:** JSON endpoints for Postman/curl testing.
- **NFRs:** Load test script (`load_test.sh`) proves concurrency (100 reqs in <1s).
- **Audit Trail:** Transaction history ensures data consistency.

## Setup
1. Clone repo.
2. `sqlite3 bank.db < schema.sql` (creates `accounts`, `transactions`, `users`).
3. `python3 app.py` (runs on `0.0.0.0:5000`).
4. Test: `curl http://localhost:5000/api/balance/1234`.

## Live Demo
Try it at `http://144.126.239.47:5000`!

## Load Test
Run `./load_test.sh`—hits `/api/balance/1234` 500 times sequentially. With a 100ms delay per request, it completes in ~55s, proving consistent latency handling.

## Data Generation
Run `python3 generate_accounts.py` to add 1000 random accounts with personal details (names, DOB, addresses, balances £100-£5000). Current total: 1061 accounts.

## Performance Testing
Run `python3 load_test_open_account.py` to simulate account openings for 60 seconds. Example: Created 150 accounts in 60.12 seconds (2.50 accounts/sec).
