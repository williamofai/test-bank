import sqlite3
import psycopg2
import bcrypt

# Connect to SQLite
sqlite_conn = sqlite3.connect('bank.db')
sqlite_cursor = sqlite_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    dbname="test_bank",
    user="test_user",
    password="TestBank2025",
    host="localhost"
)
pg_cursor = pg_conn.cursor()

# Migrate accounts (explicitly select columns in the correct order)
sqlite_cursor.execute("""
    SELECT account_number, balance, first_name, last_name, dob, 
           address_line_one, address_line_two, town, city, post_code
    FROM accounts
""")
for row in sqlite_cursor.fetchall():
    pg_cursor.execute("""
        INSERT INTO accounts (account_number, balance, first_name, last_name, dob, 
        address_line_one, address_line_two, town, city, post_code)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (account_number) DO NOTHING
    """, row)

# Migrate transactions
sqlite_cursor.execute("SELECT account_number, amount, type, timestamp FROM transactions")
for row in sqlite_cursor.fetchall():
    pg_cursor.execute("""
        INSERT INTO transactions (account_number, amount, type, timestamp)
        VALUES (%s, %s, %s, %s)
    """, row)

# Migrate users (re-hash password as bytes)
sqlite_cursor.execute("SELECT username, password FROM users")
for row in sqlite_cursor.fetchall():
    username, password = row
    # Re-hash the password to ensure it's in bytes
    hashed = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt())
    pg_cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))

# Commit and close
pg_conn.commit()
sqlite_conn.close()
pg_conn.close()

print("Migration completed successfully!")
