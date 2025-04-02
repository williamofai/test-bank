import sqlite3

# Connect to SQLite
conn = sqlite3.connect('bank.db')
cursor = conn.cursor()

# Fetch all accounts
cursor.execute("SELECT account_number, dob FROM accounts")
accounts = cursor.fetchall()

for account in accounts:
    account_number, dob = account
    # Check if dob is in DD/MM/YYYY format
    if '/' in dob:
        day, month, year = dob.split('/')
        new_dob = f"{day}{month}{year}"
    # Check if dob is in YYYY-MM-DD format
    elif '-' in dob:
        year, month, day = dob.split('-')
        new_dob = f"{day}{month}{year}"
    else:
        new_dob = dob  # Already in DDMMYYYY format
    
    # Update the dob if it was transformed
    if new_dob != dob:
        cursor.execute("UPDATE accounts SET dob = ? WHERE account_number = ?", (new_dob, account_number))

# Commit and close
conn.commit()
conn.close()

print("DOB values fixed successfully!")
