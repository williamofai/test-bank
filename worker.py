import redis
from rq import Queue, Worker
import time
import psycopg2
from psycopg2 import pool

# Redis connection
redis_conn = redis.Redis(host='localhost', port=6379, db=0)
queue = Queue(connection=redis_conn)

# Connection pool for PostgreSQL (same as in app.py)
db_pool = pool.SimpleConnectionPool(
    1, 20,  # Min and max connections
    dbname="test_bank",
    user="test_user",
    password="TestBank2025",
    host="localhost"
)

# Database connection management
def get_db_connection():
    return db_pool.getconn()

def release_db_connection(conn):
    db_pool.putconn(conn)

# Fraud check function
def check_fraud(account, amount):
    time.sleep(0.01)  # Simulate 0.01-second delay
    result = amount < 1000  # Approve if under £1000
    print(f"Fraud check for transfer of £{amount:.2f} from {account}: {'Approved' if result else 'Rejected'}")
    return result

# Process the transfer (including fraud check and database updates)
def process_transfer(from_account, to_account, amount):
    print(f"Processing transfer of £{amount:.2f} from {from_account} to {to_account}")
    
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Start a transaction and lock the rows
        cursor.execute("BEGIN")
        cursor.execute("SELECT balance FROM accounts WHERE account_number = %s FOR UPDATE", (from_account,))
        from_result = cursor.fetchone()
        cursor.execute("SELECT balance FROM accounts WHERE account_number = %s FOR UPDATE", (to_account,))
        to_result = cursor.fetchone()

        if not from_result or not to_result:
            cursor.execute("ROLLBACK")
            cursor.close()
            release_db_connection(conn)
            print(f"One or both accounts not found: {from_account}, {to_account}")
            return {"status": "failed", "message": "One or both accounts not found"}

        print(f"Balance check: Account {from_account} has £{from_result[0]:.2f}, needs £{amount:.2f}")
        if from_result[0] < amount:
            cursor.execute("ROLLBACK")
            cursor.close()
            release_db_connection(conn)
            print(f"Insufficient funds in {from_account} for transfer of £{amount:.2f}")
            return {"status": "failed", "message": f"Insufficient funds in {from_account}"}

        # Perform the fraud check after the balance check
        fraud_result = check_fraud(from_account, amount)
        if not fraud_result:
            cursor.execute("ROLLBACK")
            cursor.close()
            release_db_connection(conn)
            print(f"Transfer of £{amount:.2f} from {from_account} to {to_account} rejected by fraud check")
            return {"status": "failed", "message": f"Transfer of £{amount:.2f} from {from_account} to {to_account} rejected by fraud check"}

        # Perform the transfer
        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_number = %s", (amount, from_account))
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_number = %s", (amount, to_account))
        cursor.execute("INSERT INTO transactions (account_number, amount, type) VALUES (%s, %s, 'transfer_out')", (from_account, amount))
        cursor.execute("INSERT INTO transactions (account_number, amount, type) VALUES (%s, %s, 'transfer_in')", (to_account, amount))
        cursor.execute("COMMIT")

        cursor.close()
        release_db_connection(conn)
        print(f"Transfer of £{amount:.2f} from {from_account} to {to_account} completed successfully")
        return {"status": "success", "message": f"Transferred £{amount:.2f} from {from_account} to {to_account}"}

    except Exception as e:
        cursor.execute("ROLLBACK")
        cursor.close()
        release_db_connection(conn)
        print(f"Transfer failed: {str(e)}")
        return {"status": "failed", "message": f"Transfer failed: {str(e)}"}

if __name__ == "__main__":
    # Start the worker
    worker = Worker([queue], connection=redis_conn)
    worker.work()
