import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://144.126.239.47:5000"
OPEN_ACCOUNT_ENDPOINT = f"{BASE_URL}/open_account"
NUM_REQUESTS = 1000  # Number of accounts to open
MAX_THREADS = 10

# Sample data for account creation
NAMES = ["John", "Jane", "Alice", "Bob", "Charlie", "David", "Emma", "Frank"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"]
CITIES = ["London", "Manchester", "Birmingham", "Leeds", "Glasgow"]
TOWNS = ["West End", "Downtown", "Uptown", "Riverside", "Hillside"]

def create_account():
    first_name = random.choice(NAMES)
    last_name = random.choice(LAST_NAMES)
    dob = f"{random.randint(1, 28):02d}{random.randint(1, 12):02d}{random.randint(1970, 2000)}"
    address_line_one = f"{random.randint(1, 100)} Main St"
    address_line_two = ""
    town = random.choice(TOWNS)
    city = random.choice(CITIES)
    post_code = f"AB{random.randint(10, 99)} {random.randint(1, 9)}CD"
    initial_balance = random.uniform(0, 1000)

    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "address_line_one": address_line_one,
        "address_line_two": address_line_two,
        "town": town,
        "city": city,
        "post_code": post_code,
        "initial_balance": str(initial_balance)
    }

    try:
        start_time = time.time()
        response = requests.post(OPEN_ACCOUNT_ENDPOINT, data=payload)
        latency = time.time() - start_time
        if response.status_code == 200 and "Account" in response.text:
            print(f"Success: Created account in {latency:.3f}s")
            return latency, True
        else:
            print(f"Failed: {response.text}")
            return latency, False
    except Exception as e:
        print(f"Error: {e}")
        return 0, False

def run_load_test():
    print(f"Starting load test: {NUM_REQUESTS} account openings with {MAX_THREADS} threads...")
    start_time = time.time()
    
    latencies = []
    successes = 0
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        results = executor.map(lambda _: create_account(), range(NUM_REQUESTS))
    
    for latency, success in results:
        latencies.append(latency)
        if success:
            successes += 1
    
    total_time = time.time() - start_time
    reqs_per_sec = successes / total_time if total_time > 0 else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    print(f"\n--- Load Test Results ---")
    print(f"Completed in {total_time:.2f} seconds")
    print(f"Successful account openings: {successes}/{NUM_REQUESTS}")
    print(f"Requests per second: {reqs_per_sec:.2f}")
    print(f"Average latency: {avg_latency:.3f} seconds")

if __name__ == "__main__":
    run_load_test()
