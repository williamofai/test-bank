#!/usr/bin/env python3
import requests
import threading
import time
import random
import json
from concurrent.futures import ThreadPoolExecutor
from prometheus_client import Counter, Histogram, start_http_server

BASE_URL = "http://localhost:5000"
NUM_TRANSFERS = 5000
CONCURRENT_THREADS = 5
STATUS_TIMEOUT = 10
TRANSFER_AMOUNT_MIN = 50
TRANSFER_AMOUNT_MAX = 4999.99

SESSION = requests.Session()
VALID_ACCOUNTS = None
ACCOUNTS_LOCK = threading.Lock()

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

TRANSFER_SUCCESS = Counter('transfer_success_total', 'Total successful transfers')
TRANSFER_FAILED = Counter('transfer_failed_total', 'Total failed transfers')
TRANSFER_LATENCY = Histogram('transfer_latency_seconds', 'Transfer latency in seconds', buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300])

def get_valid_accounts():
    global VALID_ACCOUNTS, SESSION
    with ACCOUNTS_LOCK:
        if VALID_ACCOUNTS is None:
            print("Fetching valid accounts...")
            SESSION = requests.Session()
            login_data = {"username": "testuser", "password": "password123"}
            response = SESSION.post(f"{BASE_URL}/login", json=login_data, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            token = response.json()['access_token']
            HEADERS['Authorization'] = f"Bearer {token}"
            response = SESSION.get(f"{BASE_URL}/list", headers=HEADERS)
            response.raise_for_status()
            accounts = response.json()
            if not accounts:
                raise Exception("No valid accounts found")
            VALID_ACCOUNTS = [acc for acc in accounts if acc['balance'] > 50]
            print(f"Loaded {len(VALID_ACCOUNTS)} valid accounts")
    return VALID_ACCOUNTS

def make_transfer(from_account=None, to_account=None, amount=None):
    accounts = get_valid_accounts()
    if not accounts:
        raise Exception("No valid accounts available")
    from_account = from_account or random.choice(accounts)['account_number']
    to_account = to_account or random.choice([a for a in accounts if a['account_number'] != from_account])['account_number']
    amount = amount or random.uniform(TRANSFER_AMOUNT_MIN, TRANSFER_AMOUNT_MAX)
    job_data = {'from_account': from_account, 'to_account': to_account, 'amount': amount}
    start_time = time.time()
    print(f"Making transfer: from={from_account}, to={to_account}, amount={amount}")
    for attempt in range(3):
        try:
            response = SESSION.post(f"{BASE_URL}/transfer", json=job_data, headers=HEADERS)
            response.raise_for_status()
            job_id = response.json()['transfer_id']
            return job_id, start_time, amount
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                print(f"Retry {attempt+1}/3 for transfer: {str(e)}")
                time.sleep(1)
                continue
            raise Exception(f"Failed after 3 attempts: {str(e)}")

def check_transfer_status(job_id, start_time):
    enqueue_time = time.time() - start_time
    timeout = start_time + STATUS_TIMEOUT
    while time.time() < timeout:
        for attempt in range(5):
            try:
                response = SESSION.get(f"{BASE_URL}/transfer_status/{job_id}", headers=HEADERS)
                print(f"Checking status for {job_id}: HTTP {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    print(f"Status response for {job_id}: {result}")
                    if not isinstance(result, dict):
                        raise ValueError(f"Expected dict, got {type(result)}: {result}")
                    total_time = time.time() - start_time
                    status = result['status']
                    print(f"Status for {job_id}: {status}")
                    return status, result.get('result', {}), enqueue_time, total_time
                elif response.status_code == 202:
                    print(f"Status for {job_id}: still processing")
                    time.sleep(0.2)
                    break
                else:
                    raise Exception(f"Unexpected status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                if attempt < 4:
                    print(f"Retry {attempt+1}/5 for status {job_id}: {str(e)}")
                    time.sleep(0.5)
                    continue
                raise Exception(f"Failed after 5 attempts: {str(e)}")
    print(f"Timeout for {job_id} after {STATUS_TIMEOUT}s")
    return "timeout", {"message": "Transfer timed out"}, enqueue_time, time.time() - start_time

def run_transfer(transfer_id):
    try:
        job_id, start_time, amount = make_transfer()
        print(f"Transfer {transfer_id}: Enqueued job_id={job_id}")
        status, result, enqueue_time, total_time = check_transfer_status(job_id, start_time)
        print(f"Transfer {transfer_id}: Status={status}, Result={result}")
        if status == "completed":
            TRANSFER_SUCCESS.inc()
            TRANSFER_LATENCY.observe(total_time)
            return True, amount, enqueue_time, total_time, None
        else:
            TRANSFER_FAILED.inc()
            reason = result.get('message', status) if isinstance(result, dict) else str(result)
            return False, amount, enqueue_time, total_time, reason
    except Exception as e:
        TRANSFER_FAILED.inc()
        print(f"Transfer {transfer_id} failed: {str(e)}")
        return False, None, None, None, str(e)

def main():
    start_http_server(8000)
    print("Starting load test...")
    start_time = time.time()

    get_valid_accounts()

    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as executor:
        futures = [executor.submit(run_transfer, i) for i in range(NUM_TRANSFERS)]
        results = [future.result() for future in futures]

    end_time = time.time()
    total_time = end_time - start_time

    successful_transfers = sum(1 for result in results if result[0])
    failed_transfers = NUM_TRANSFERS - successful_transfers
    requests_per_second = NUM_TRANSFERS / total_time
    successful_enqueues = [result[2] for result in results if result[0] and result[2] is not None]
    successful_totals = [result[3] for result in results if result[0] and result[3] is not None]
    avg_enqueue_latency = sum(successful_enqueues) / len(successful_enqueues) if successful_enqueues else 0
    avg_total_latency = sum(successful_totals) / len(successful_totals) if successful_totals else 0
    transfers_above_1000 = sum(1 for result in results if result[1] is not None and result[1] > 1000)
    for result in results:
        if not result[0]:
            print(f"Failed transfer reason: {result[4]}")
    fraud_check_failures = sum(1 for result in results if not result[0] and result[4] and "rejected by fraud check" in result[4])
    insufficient_funds_failures = sum(1 for result in results if not result[0] and result[4] and "Insufficient funds" in result[4])
    timeout_failures = sum(1 for result in results if not result[0] and result[4] and "Transfer timed out" in result[4])
    connection_failures = sum(1 for result in results if not result[0] and result[4] and "Connection" in result[4])
    other_failures = failed_transfers - fraud_check_failures - insufficient_funds_failures - timeout_failures - connection_failures

    print("--- Load Test Results ---")
    print(f"Completed in {total_time:.2f} seconds")
    print(f"Successful transfers: {successful_transfers}/{NUM_TRANSFERS}")
    print(f"Requests per second: {requests_per_second:.2f}")
    print(f"Average enqueue latency (successful transfers): {avg_enqueue_latency:.3f} seconds")
    print(f"Average total latency (successful transfers): {avg_total_latency:.3f} seconds")
    print("\n--- Failure Breakdown ---")
    print(f"Transfers with amount >£1000: {transfers_above_1000}")
    print(f"Fraud check failures: {fraud_check_failures}")
    print(f"Insufficient funds failures: {insufficient_funds_failures}")
    print(f"Timeout failures: {timeout_failures}")
    print(f"Connection failures: {connection_failures}")
    print(f"Other failures: {other_failures}")
    print("\n--- Prometheus Metrics ---")
    print(f"Total transfers processed (success): {TRANSFER_SUCCESS._value.get()}")
    print(f"Total transfers processed (failed): {TRANSFER_FAILED._value.get()}")

if __name__ == "__main__":
    main()
