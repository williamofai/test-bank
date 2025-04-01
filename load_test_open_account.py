import requests
import time
import random
import string
import threading

# Sample data pools
first_names = ['John', 'Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'James', 'Sophia']
last_names = ['Doe', 'Smith', 'Brown', 'Wilson', 'Taylor', 'Clark', 'Lewis', 'Walker']
towns = ['Smallville', 'Greentown', 'Bluetown', 'Redhill']
cities = ['London', 'Manchester', 'Birmingham', 'Leeds']
streets = ['High Street', 'Main Road', 'Park Lane', 'Church Street']

def open_account():
    url = "http://144.126.239.47:5000/open_account"
    data = {
        'first_name': random.choice(first_names),
        'last_name': random.choice(last_names),
        'dob': f"{random.randint(1960, 2005)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        'address_line_one': f"{random.randint(1, 999)} {random.choice(streets)}",
        'address_line_two': '' if random.random() < 0.7 else f"Flat {random.randint(1, 20)}",
        'town': random.choice(towns),
        'city': random.choice(cities),
        'post_code': f"{''.join(random.choices(string.ascii_uppercase, k=2))}{random.randint(1, 9)} {random.randint(1, 9)}{''.join(random.choices(string.ascii_uppercase, k=2))}",
        'initial_balance': round(random.uniform(100, 5000), 2)
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            return True
    except:
        pass
    return False

def load_test(duration):
    start_time = time.time()
    success_count = 0
    threads = []

    def worker():
        nonlocal success_count
        while time.time() - start_time < duration:
            if open_account():
                success_count += 1

    # Start 10 threads to simulate concurrent users
    for _ in range(10):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    # Wait for duration or all threads to finish
    for thread in threads:
        thread.join(timeout=duration - (time.time() - start_time))

    elapsed = time.time() - start_time
    print(f"Created {success_count} accounts in {elapsed:.2f} seconds")
    print(f"Rate: {success_count / elapsed:.2f} accounts per second")

if __name__ == "__main__":
    duration = 60  # Run for 60 seconds
    load_test(duration)
