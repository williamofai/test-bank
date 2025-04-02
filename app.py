from flask import Flask, request, jsonify, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import psycopg2
from psycopg2 import pool
import time
import random
import string
import bcrypt
import redis
from rq import Queue

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    raise ValueError("No SECRET_KEY set for Flask application. Set the SECRET_KEY environment variable.")

# Connection pool for PostgreSQL (updated max connections to 40)
db_pool = pool.SimpleConnectionPool(
    1, 40,  # Increased max connections to 40 to handle load from Gunicorn and RQ workers
    dbname="test_bank",
    user="test_user",
    password="TestBank2025",
    host="localhost"
)

# Redis and RQ setup
redis_conn = redis.Redis(host='localhost', port=6379, db=0)
queue = Queue(connection=redis_conn)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    if user:
        return User(user[0])
    return None

# Database connection management
def get_db_connection():
    return db_pool.getconn()

def release_db_connection(conn):
    db_pool.putconn(conn)

# Basic CSS for all pages
BASE_STYLE = """
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #333; padding: 8px; }
        th { background-color: #f2f2f2; }
        .success { color: green; }
        .error { color: red; }
        form { margin-top: 10px; }
        input[type="text"], input[type="number"], input[type="password"] { padding: 5px; }
        input[type="submit"] { padding: 5px 10px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }
    </style>
"""

@app.route('/')
def home():
    return f"""
        {BASE_STYLE}
        <h1>Test Bank</h1>
        <form action="/check" method="POST">
            Account Number: <input type="text" name="account" required>
            <input type="submit" value="Check Balance">
        </form>
        <p><a href="/deposit">Make a Deposit</a> | <a href="/withdraw">Withdraw Funds</a> | <a href="/transfer">Transfer Funds</a> | <a href="/history">View Transaction History</a> | <a href="/list">List Accounts</a> | <a href="/open_account">Open Account</a> | <a href="/register">Register</a> | <a href="/login">Login</a> | <a href="/logout">Logout</a></p>
    """

@app.route('/check', methods=['GET', 'POST'])
def check_balance():
    if request.method == 'POST':
        account = request.form['account']
    else:
        account = request.args.get('account', '1234')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT account_number, balance, first_name, last_name, dob, 
        address_line_one, address_line_two, town, city, post_code 
        FROM accounts WHERE account_number = %s
    """, (account,))
    result = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    if result:
        balance = "{:.2f}".format(result[1])
        details = f"""
            <p class='success'>Account {result[0]}: £{balance} available</p>
            <table>
                <tr><th>Field</th><th>Value</th></tr>
                <tr><td>First Name</td><td>{result[2]}</td></tr>
                <tr><td>Last Name</td><td>{result[3]}</td></tr>
                <tr><td>DOB (DDMMYYYY)</td><td>{result[4]}</td></tr>
                <tr><td>Address</td><td>{result[5]} {result[6]}, {result[7]}, {result[8]}, {result[9]}</td></tr>
            </table>
        """
        return f"{BASE_STYLE}<h1>Test Bank</h1>{details}<a href='/'>Back</a>"
    return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Account {account} not found</p><a href='/'>Back</a>"

@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    if request.method == 'POST':
        account = request.form['account']
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Amount must be positive</p><a href='/deposit'>Back</a>", 400
        except ValueError:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Invalid amount</p><a href='/deposit'>Back</a>", 400
        
        # Enqueue fraud check
        job = queue.enqueue('worker.check_fraud', account, amount)
        while not job.is_finished:
            time.sleep(0.1)
        fraud_result = job.result
        
        if not fraud_result:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Deposit of £{amount:.2f} to {account} rejected by fraud check</p><a href='/'>Back</a>", 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_number = %s", (amount, account))
        if cursor.rowcount == 0:
            cursor.close()
            release_db_connection(conn)
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Account {account} not found</p><a href='/'>Back</a>", 400
        cursor.execute("INSERT INTO transactions (account_number, amount, type) VALUES (%s, %s, 'deposit')", (account, amount))
        conn.commit()
        cursor.execute("SELECT balance FROM accounts WHERE account_number = %s", (account,))
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Deposited £{amount:.2f} to {account}. New balance: £{result[0]:.2f}</p><a href='/'>Back</a>", 200
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Deposit</h1>
        <form action="/deposit" method="POST">
            Account Number: <input type="text" name="account" required><br>
            Amount: <input type="number" name="amount" step="0.01" min="0.01" required><br>
            <input type="submit" value="Deposit">
        </form>
        <a href="/">Back</a>
    """

@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    if request.method == 'POST':
        account = request.form['account']
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Amount must be positive</p><a href='/withdraw'>Back</a>", 400
        except ValueError:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Invalid amount</p><a href='/withdraw'>Back</a>", 400
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_number = %s", (account,))
        result = cursor.fetchone()
        if result:
            if result[0] >= amount:
                cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_number = %s", (amount, account))
                cursor.execute("INSERT INTO transactions (account_number, amount, type) VALUES (%s, %s, 'withdraw')", (account, amount))
                conn.commit()
                cursor.execute("SELECT balance FROM accounts WHERE account_number = %s", (account,))
                new_balance = cursor.fetchone()[0]
                cursor.close()
                release_db_connection(conn)
                return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Withdrew £{amount:.2f} from {account}. New balance: £{new_balance:.2f}</p><a href='/'>Back</a>", 200
            cursor.close()
            release_db_connection(conn)
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Insufficient funds in {account}</p><a href='/'>Back</a>", 400
        cursor.close()
        release_db_connection(conn)
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Account {account} not found</p><a href='/'>Back</a>", 400
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Withdraw</h1>
        <form action="/withdraw" method="POST">
            Account Number: <input type="text" name="account" required><br>
            Amount: <input type="number" name="amount" step="0.01" min="0.01" required><br>
            <input type="submit" value="Withdraw">
        </form>
        <a href="/">Back</a>
    """

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if request.method == 'POST':
        from_account = request.form['from_account']
        to_account = request.form['to_account']
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Amount must be positive</p><a href='/transfer'>Back</a>", 400
        except ValueError:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Invalid amount</p><a href='/transfer'>Back</a>", 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if both accounts exist (but don't check balance here)
        cursor.execute("SELECT 1 FROM accounts WHERE account_number = %s", (from_account,))
        from_result = cursor.fetchone()
        cursor.execute("SELECT 1 FROM accounts WHERE account_number = %s", (to_account,))
        to_result = cursor.fetchone()
        
        if not from_result or not to_result:
            cursor.close()
            release_db_connection(conn)
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>One or both accounts not found</p><a href='/transfer'>Back</a>", 400
        
        # Enqueue the transfer processing (including balance check and fraud check)
        job = queue.enqueue('worker.process_transfer', from_account, to_account, amount)
        
        # Return immediately with a "processing" message and a link to check status
        cursor.close()
        release_db_connection(conn)
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Transfer of £{amount:.2f} from {from_account} to {to_account} is being processed. <a href='/transfer_status/{job.id}'>Check Status (Job ID: {job.id})</a></p><a href='/'>Back</a>", 200
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Transfer Funds</h1>
        <form action="/transfer" method="POST">
            From Account: <input type="text" name="from_account" required><br>
            To Account: <input type="text" name="to_account" required><br>
            Amount: <input type="number" name="amount" step="0.01" min="0.01" required><br>
            <input type="submit" value="Transfer">
        </form>
        <a href="/">Back</a>
    """

@app.route('/transfer_status/<job_id>', methods=['GET'])
@login_required
def transfer_status(job_id):
    from rq.job import Job
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        if job.is_finished:
            return jsonify({"status": "completed", "result": job.result}), 200
        elif job.is_failed:
            return jsonify({"status": "failed", "message": str(job.exc_info)}), 500
        else:
            return jsonify({"status": "processing"}), 202
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid job ID: {str(e)}"}), 404

@app.route('/history', methods=['GET', 'POST'])
@login_required
def history():
    if request.method == 'POST':
        account = request.form['account']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, type, timestamp FROM transactions WHERE account_number = %s ORDER BY timestamp DESC", (account,))
        transactions = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)
        if transactions:
            table = "<table><tr><th>Amount</th><th>Type</th><th>Time</th></tr>"
            for t in transactions:
                table += f"<tr><td>£{t[0]:.2f}</td><td>{t[1]}</td><td>{t[2]}</td></tr>"
            table += "</table>"
            return f"{BASE_STYLE}<h1>Test Bank - History</h1><p>Account {account}</p>{table}<a href='/'>Back</a>", 200
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>No transactions for {account}</p><a href='/'>Back</a>", 404
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Transaction History</h1>
        <form action="/history" method="POST">
            Account Number: <input type="text" name="account" required><br>
            <input type="submit" value="View History">
        </form>
        <a href="/">Back</a>
    """

@app.route('/api/balance/<account>', methods=['GET'])
def api_balance(account):
    time.sleep(0.1)  # 100ms delay
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM accounts WHERE account_number = %s", (account,))
    result = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    if result:
        return jsonify({"account": account, "balance": result[0]}), 200
    return jsonify({"error": "Account not found"}), 404

@app.route('/api/history/<account>', methods=['GET'])
def api_history(account):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT amount, type, timestamp FROM transactions WHERE account_number = %s ORDER BY timestamp DESC", (account,))
    transactions = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    if transactions:
        return jsonify([{"amount": t[0], "type": t[1], "timestamp": str(t[2])} for t in transactions]), 200
    return jsonify({"error": "No transactions found"}), 404

@app.route('/list', methods=['GET', 'POST'])
def list_accounts():
    try:
        page = int(request.args.get('page', 1))
        per_page = 50  # 50 accounts per page
        offset = (page - 1) * per_page
        search_query = request.form.get('search', '') if request.method == 'POST' else request.args.get('search', '')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Count total accounts with search filter
        if search_query:
            cursor.execute("""
                SELECT COUNT(*) FROM accounts
                WHERE account_number LIKE %s OR first_name LIKE %s OR last_name LIKE %s
            """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            cursor.execute("SELECT COUNT(*) FROM accounts")
        total = cursor.fetchone()[0]

        # Fetch accounts with search filter
        if search_query:
            cursor.execute("""
                SELECT account_number, first_name, last_name, balance FROM accounts
                WHERE account_number LIKE %s OR first_name LIKE %s OR last_name LIKE %s
                LIMIT %s OFFSET %s
            """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', per_page, offset))
        else:
            cursor.execute("""
                SELECT account_number, first_name, last_name, balance FROM accounts
                LIMIT %s OFFSET %s
            """, (per_page, offset))
        accounts = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)

        total_pages = (total + per_page - 1) // per_page
        table = "<table><tr><th>Account Number</th><th>First Name</th><th>Last Name</th><th>Balance</th></tr>"
        for acc in accounts:
            table += f"<tr><td><a href='/check?account={acc[0]}'>{acc[0]}</a></td><td>{acc[1]}</td><td>{acc[2]}</td><td>£{acc[3]:.2f}</td></tr>"
        table += "</table>"

        pagination = f"<p>Page {page} of {total_pages}</p>"
        if page > 1:
            pagination += f"<a href='/list?page={page-1}&search={search_query}'>Previous</a> "
        if page < total_pages:
            pagination += f"<a href='/list?page={page+1}&search={search_query}'>Next</a>"

        search_form = f"""
            <form action="/list" method="POST">
                Search: <input type="text" name="search" value="{search_query}">
                <input type="submit" value="Search">
            </form>
        """

        return f"{BASE_STYLE}<h1>Test Bank - Account List</h1>{search_form}{table}{pagination}<p><a href='/'>Back</a></p>", 200

    except Exception as e:
        # Log the error for debugging
        print(f"Error in /list endpoint: {str(e)}")
        # If there's an open connection, close it
        if 'conn' in locals() and conn:
            if 'cursor' in locals() and cursor:
                cursor.close()
            release_db_connection(conn)
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>An error occurred while fetching accounts: {str(e)}</p><a href='/'>Back</a>", 500

@app.route('/open_account', methods=['GET', 'POST'])
def open_account():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        dob = request.form['dob']
        address_line_one = request.form['address_line_one']
        address_line_two = request.form['address_line_two']
        town = request.form['town']
        city = request.form['city']
        post_code = request.form['post_code']
        initial_balance = float(request.form['initial_balance'])
        
        # Use a single connection from the pool
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate a unique 6-digit account number
        while True:
            account_number = ''.join(random.choices(string.digits, k=6))
            cursor.execute("SELECT 1 FROM accounts WHERE account_number = %s", (account_number,))
            if not cursor.fetchone():
                break
        
        # Insert the new account
        cursor.execute("""
            INSERT INTO accounts (account_number, balance, first_name, last_name, dob, 
            address_line_one, address_line_two, town, city, post_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (account_number, initial_balance, first_name, last_name, dob, 
              address_line_one, address_line_two, town, city, post_code))
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Account {account_number} created successfully!</p><a href='/'>Back</a>", 200
    
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Open Account</h1>
        <form action="/open_account" method="POST">
            First Name: <input type="text" name="first_name" required><br>
            Last Name: <input type="text" name="last_name" required><br>
            DOB (DDMMYYYY): <input type="text" name="dob" required><br>
            Address Line 1: <input type="text" name="address_line_one" required><br>
            Address Line 2: <input type="text" name="address_line_two"><br>
            Town: <input type="text" name="town" required><br>
            City: <input type="text" name="city" required><br>
            Post Code: <input type="text" name="post_code" required><br>
            Initial Balance: <input type="number" name="initial_balance" step="0.01" min="0" value="0.00" required><br>
            <input type="submit" value="Open Account">
        </form>
        <a href="/">Back</a>
    """

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Validate input
        if not username or not password:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Username and password are required</p><a href='/register'>Try again</a>", 400
        
        # Check if username already exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            release_db_connection(conn)
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Username already exists</p><a href='/register'>Try again</a>", 400
        
        # Hash the password and store the user
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password.decode('utf-8')))
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Registration successful! Please <a href='/login'>login</a>.</p>", 200
    
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Register</h1>
        <form action="/register" method="POST">
            Username: <input type="text" name="username" required><br>
            Password: <input type="password" name="password" required><br>
            <input type="submit" value="Register">
        </form>
        <a href="/">Back</a>
    """

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        
        # Updated to handle memoryview issue with psycopg2
        if result:
            stored_password = result[0].tobytes() if isinstance(result[0], memoryview) else result[0]
            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8') if isinstance(stored_password, str) else stored_password):
                user = User(username)
                login_user(user)
                return redirect(url_for('home'))
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Invalid username or password</p><a href='/login'>Try again</a>", 401
    
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Login</h1>
        <form action="/login" method="POST">
            Username: <input type="text" name="username" required><br>
            Password: <input type="password" name="password" required><br>
            <input type="submit" value="Login">
        </form>
        <a href="/">Back</a>
    """

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
