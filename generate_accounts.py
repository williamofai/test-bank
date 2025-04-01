import sqlite3
import random
import string

# Sample data pools
first_names = ['John', 'Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'James', 'Sophia']
last_names = ['Doe', 'Smith', 'Brown', 'Wilson', 'Taylor', 'Clark', 'Lewis', 'Walker']
towns = ['Smallville', 'Greentown', 'Bluetown', 'Redhill']
cities = ['London', 'Manchester', 'Birmingham', 'Leeds']
streets = ['High Street', 'Main Road', 'Park Lane', 'Church Street']

conn = sqlite3.connect('bank.db')
cursor = conn.cursor()

for i in range(10):  # 10 random accounts
    acct_num = ''.join(random.choices(string.digits, k=6))  # 6-digit account number
    balance = round(random.uniform(100, 5000), 2)  # Random balance £100-£5000
    first = random.choice(first_names)
    last = random.choice(last_names)
    dob = f"{random.randint(1960, 2005)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    addr1 = f"{random.randint(1, 999)} {random.choice(streets)}"
    addr2 = '' if random.random() < 0.7 else f"Flat {random.randint(1, 20)}"
    town = random.choice(towns)
    city = random.choice(cities)
    postcode = f"{''.join(random.choices(string.ascii_uppercase, k=2))}{random.randint(1, 9)} {random.randint(1, 9)}{''.join(random.choices(string.ascii_uppercase, k=2))}"
    
    cursor.execute("""
        INSERT OR IGNORE INTO accounts (account_number, balance, first_name, last_name, dob, 
        address_line_one, address_line_two, town, city, post_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (acct_num, balance, first, last, dob, addr1, addr2, town, city, postcode))

conn.commit()
conn.close()
print("Added 10 random accounts!")
