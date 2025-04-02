import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import threading

# Configuration
BASE_URL = "http://144.126.239.47:5000"
TRANSFER_ENDPOINT = f"{BASE_URL}/transfer"
STATUS_ENDPOINT = f"{BASE_URL}/transfer_status"
LIST_ENDPOINT = f"{BASE_URL}/list"
NUM_REQUESTS = 500  # Total transfers to simulate
MAX_THREADS = 20    # Increased to 20 concurrent threads

# Login credentials (to access protected endpoint)
LOGIN_URL = f"{BASE_URL}/login"
LOGIN_DATA = {"username": "testuser", "password": "password123"}

# Thread-local storage for sessions
thread_local = threading.local()

def get_session():
    """
    Returns a thread-local requests.Session object.
    Creates a new session if one doesn't exist for the current thread.
    """
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
        # Log in immediately for this thread
        print(f"Thread {threading.current_thread().name}: Creating new session and logging in...")
        login_response = thread_local.session.post(LOGIN_URL, data=LOGIN_DATA, allow_redirects=False)
        if login_response.status_code == 302:
            # Follow the redirect to the home page
            home_response = thread_local.session.get(BASE_URL)
            if home_response.status_code == 200 and "Test Bank" in home_response.text and "Check Balance" in home_response.text:
                print(f"Thread {threading.current_thread().name}: Login successful")
                print(f"Thread {threading.current_thread().name}: Session cookies: {thread_local.session.cookies.get_dict()}")
            else:
                print(f"Thread {threading.current_thread().name}: Login failed: Did not redirect to home page")
                print(f"Home page response: {home_response.text}")
        else:
            print(f"Thread {threading.current_thread().name}: Login failed: Status {login_response.status_code} - {login_response.text}")
    return thread_local.session

# Ensure the session is authenticated
def ensure_authenticated():
    """
    Ensures the session is authenticated by checking access to a protected endpoint.
    Uses a thread-local session to avoid race conditions.
    Returns True if authenticated, False otherwise.
    """
    session = get_session()
    # Check if we're already authenticated by accessing a protected endpoint
    response = session.get(LIST_ENDPOINT, allow_redirects=False)
    if response.status_code == 200 and "Test Bank - Account List" in response.text:
        print(f"Thread {threading.current_thread().name}: Session is authenticated")
        print(f"Thread {threading.current_thread().name}: Session cookies: {session.cookies.get_dict()}")
        return True
    
    # If not authenticated, attempt to log in again
    print(f"Thread {threading.current_thread().name}: Session not authenticated, attempting to log in...")
    login_response = session.post(LOGIN_URL, data=LOGIN_DATA, allow_redirects=False)
    if login_response.status_code == 302:
        # Follow the redirect to the home page
        home_response = session.get(BASE_URL)
        if home_response.status_code == 200 and "Test Bank" in home_response.text and "Check Balance" in home_response.text:
            print(f"Thread {threading.current_thread().name}: Login successful")
            print(f"Thread {threading.current_thread().name}: Session cookies: {session.cookies.get_dict()}")
            return True
        else:
            print(f"Thread {threading.current_thread().name}: Login failed: Did not redirect to home page")
            print(f"Home page response: {home_response.text}")
            return False
    print(f"Thread {threading.current_thread().name}: Login failed: Status {login_response.status_code} - {login_response.text}")
    return False

# Fetch valid account numbers from /list
def get_valid_accounts():
    """
    Fetches a list of valid account numbers by querying the /list endpoint.
    Requires logging in first, as /list is a protected route.
    Returns a list of account numbers as strings.
    """
    # Use a single session for this initial request
    session = requests.Session()
    print("Fetching valid accounts from /list...")
    login_response = session.post(LOGIN_URL, data=LOGIN_DATA, allow_redirects=False)
    if login_response.status_code != 302:
        print(f"Initial login failed: Status {login_response.status_code} - {login_response.text}")
        return []
    
    # Follow the redirect to the home page
    home_response = session.get(BASE_URL)
    if home_response.status_code != 200 or "Test Bank" not in home_response.text:
        print(f"Failed to access home page after login: {home_response.text}")
        return []
    
    # Fetch the /list page
    response = session.get(LIST_ENDPOINT, allow_redirects=False)
    if response.status_code != 200:
        print(f"Failed to fetch account list: Status {response.status_code} - {response.text}")
        return []
    
    # Parse the HTML to extract account numbers
    soup = BeautifulSoup(response.text, 'html.parser')
    accounts = []
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')[1:]  # Skip header row
        for row in rows:
            cols = row.find_all('td')
            if cols:
                account_number = cols[0].text.strip()  # First column is account number
                if account_number.isdigit():
                    accounts.append(account_number)
    print(f"Fetched {len(accounts)} valid accounts")
    return accounts

# Generate random account pairs from valid accounts
def get_random_account_pair(valid_accounts):
    """
    Selects two different random account numbers from the list of valid accounts.
    Args:
        valid_accounts (list): List of valid account numbers.
    Returns:
        tuple: (from_account, to_account) as strings.
    """
    if len(valid_accounts) < 2:
        raise ValueError("Not enough valid accounts to test!")
    from_account = random.choice(valid_accounts)
    to_account = random.choice(valid_accounts)
    while to_account == from_account:  # Ensure different accounts
        to_account = random.choice(valid_accounts)
    return from_account, to_account

# Check the status of a transfer job
def check_transfer_status(job_id):
    """
    Polls the /transfer_status/<job_id> endpoint until the job is finished.
    Args:
        job_id (str): The ID of the RQ job.
    Returns:
        tuple: (success, message) where success is a boolean indicating if the transfer succeeded,
               and message is the result message from the job.
    """
    session = get_session()
    status_url = f"{STATUS_ENDPOINT}/{job_id}"
    while True:
        # Ensure we're authenticated before making the request
        if not ensure_authenticated():
            return False, "Failed to authenticate for status check"
        
        response = session.get(status_url, allow_redirects=False)
        if response.status_code == 202:  # Job is still processing
            time.sleep(0.05)  # Wait before polling again
            continue
        elif response.status_code != 200:
            return False, f"Failed to check status: {response.text} (Status: {response.status_code})"
        
        status_data = response.json()
        status = status_data.get("status")
        
        if status == "completed":
            result = status_data.get("result", {})
            if result.get("status") == "success":
                return True, result.get("message", "Transfer completed")
            else:
                return False, result.get("message", "Transfer failed")
        elif status == "failed":
            return False, status_data.get("message", "Job failed")
        elif status == "error":
            return False, status_data.get("message", "Invalid job ID")
        else:
            time.sleep(0.05)  # Wait before polling again

# Single transfer request
def make_transfer(valid_accounts, large_amounts_counter):
    """
    Makes a single transfer request using two random valid accounts and waits for the job to complete.
    Args:
        valid_accounts (list): List of valid account numbers.
        large_amounts_counter (list): A list to track the number of transfers >£1000 (used for analysis).
    Returns:
        tuple: (latency, success, message, amount) where latency is the request time in seconds,
               success is a boolean indicating if the transfer was successful,
               message is the result message, and amount is the transfer amount.
    """
    from_account, to_account = get_random_account_pair(valid_accounts)
    amount = random.uniform(50.0, 2000.0)  # £50 to £2000
    if amount > 1000:
        large_amounts_counter[0] += 1  # Increment counter for amounts >£1000
    payload = {
        "from_account": str(from_account),
        "to_account": str(to_account),
        "amount": str(amount)
    }
    try:
        # Ensure we're authenticated before making the request
        if not ensure_authenticated():
            return 0, False, "Failed to authenticate for transfer request", amount
        
        session = get_session()
        start_time = time.time()
        response = session.post(TRANSFER_ENDPOINT, data=payload, allow_redirects=False)
        latency = time.time() - start_time
        
        if response.status_code != 200:
            print(f"Failed to enqueue transfer: {response.text} (Status: {response.status_code})")
            return latency, False, response.text, amount
        
        # Extract job ID from the response
        soup = BeautifulSoup(response.text, 'html.parser')
        success_message = soup.find('p', class_='success')
        if not success_message:
            print(f"Failed to enqueue transfer: {response.text}")
            return latency, False, "Failed to enqueue transfer", amount
        
        # Extract job ID (e.g., "Job ID: <job_id>")
        job_id_text = success_message.text
        job_id = job_id_text.split("Job ID: ")[-1].split(")")[0].strip()
        
        # Wait for the job to complete and check its status
        success, message = check_transfer_status(job_id)
        if success:
            print(f"Success: Transfer £{amount:.2f} from {from_account} to {to_account} in {latency:.3f}s - {message}")
        else:
            print(f"Failed transfer: £{amount:.2f} from {from_account} to {to_account} - {message}")
        return latency, success, message, amount
    
    except Exception as e:
        print(f"Error: {e}")
        return 0, False, str(e), amount

# Main load test
def run_load_test():
    """
    Runs the load test by simulating NUM_REQUESTS transfers using MAX_THREADS concurrent threads.
    Prints the results, including total time, success rate, throughput, average latency,
    and a breakdown of failure reasons.
    """
    # Fetch valid accounts
    valid_accounts = get_valid_accounts()
    if not valid_accounts:
        print("No valid accounts found! Aborting test.")
        return
    
    print(f"Starting load test: {NUM_REQUESTS} transfers with {MAX_THREADS} threads...")
    start_time = time.time()
    
    latencies = []
    successes = 0
    messages = []
    amounts = []
    large_amounts_counter = [0]  # Counter for transfers >£1000 (mutable list for thread safety)
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        results = executor.map(lambda _: make_transfer(valid_accounts, large_amounts_counter), range(NUM_REQUESTS))
    
    for latency, success, message, amount in results:
        latencies.append(latency)
        messages.append(message)
        amounts.append(amount)
        if success:
            successes += 1
    
    total_time = time.time() - start_time
    reqs_per_sec = NUM_REQUESTS / total_time if total_time > 0 else 0  # Use total requests, not successes
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    # Analyze failure reasons
    fraud_check_failures = sum(1 for msg in messages if "rejected by fraud check" in msg)
    insufficient_funds_failures = sum(1 for msg in messages if "Insufficient funds" in msg)
    other_failures = (NUM_REQUESTS - successes) - (fraud_check_failures + insufficient_funds_failures)
    
    print(f"\n--- Load Test Results ---")
    print(f"Completed in {total_time:.2f} seconds")
    print(f"Successful transfers: {successes}/{NUM_REQUESTS}")
    print(f"Requests per second: {reqs_per_sec:.2f}")
    print(f"Average latency: {avg_latency:.3f} seconds")
    print(f"\n--- Failure Breakdown ---")
    print(f"Transfers with amount >£1000: {large_amounts_counter[0]}")
    print(f"Fraud check failures: {fraud_check_failures}")
    print(f"Insufficient funds failures: {insufficient_funds_failures}")
    print(f"Other failures: {other_failures}")

if __name__ == "__main__":
    run_load_test()
