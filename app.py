from flask import Flask, request, jsonify
import sqlite3
import time

app = Flask(__name__)

# Fake fraud check stub
def check_fraud(account, amount):
    time.sleep(1)  # Simulate 1-second delay
    return amount < 1000  # Approve if under £1000

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
        input[type="text"], input[type="number"] { padding: 5px; }
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
        <p><a href="/deposit">Make a Deposit</a> | <a href="/withdraw">Withdraw Funds</a> | <a href="/history">View Transaction History</a> | <a href="/login">Login</a></p>
    """

@app.route('/check', methods=['GET', 'POST'])
def check_balance():
    if request.method == 'POST':
        account = request.form['account']
    else:  # GET
        account = request.args.get('account', '1234')  # Default to 1234
    conn = sqlite3.connect('bank.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE account_number = ?", (account,))
    result = cursor.fetchone()
    conn.close()
    if result:
        balance = "{:.2f}".format(result[1])
        details = f"""
            <p class='success'>Account {account}: £{balance} available</p>
            <p>First Name: {result[2]}</p>
            <p>Last Name: {result[3]}</p>
            <p>DOB: {result[4]}</p>
            <p>Address: {result[5]} {result[6]}, {result[7]}, {result[8]}, {result[9]}</p>
        """
        return f"{BASE_STYLE}<h1>Test Bank</h1>{details}<a href='/'>Back</a>"
    return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Account {account} not found</p><a href='/'>Back</a>"

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        account = request.form['account']
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Amount must be positive</p><a href='/deposit'>Back</a>"
        except ValueError:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Invalid amount</p><a href='/deposit'>Back</a>"
        
        if not check_fraud(account, amount):
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Deposit of £{amount:.2f} to {account} rejected by fraud check</p><a href='/'>Back</a>"
        
        conn = sqlite3.connect('bank.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE account_number = ?", (amount, account))
        if cursor.rowcount == 0:
            conn.close()
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Account {account} not found</p><a href='/'>Back</a>"
        cursor.execute("INSERT INTO transactions (account_number, amount, type) VALUES (?, ?, 'deposit')", (account, amount))
        conn.commit()
        cursor.execute("SELECT balance FROM accounts WHERE account_number = ?", (account,))
        result = cursor.fetchone()
        conn.close()
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Deposited £{amount:.2f} to {account}. New balance: £{result[0]:.2f}</p><a href='/'>Back</a>"
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
def withdraw():
    if request.method == 'POST':
        account = request.form['account']
        try:
            amount = float(request.form['amount'])
            if amount <= 0:
                return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Amount must be positive</p><a href='/withdraw'>Back</a>"
        except ValueError:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Invalid amount</p><a href='/withdraw'>Back</a>"
        conn = sqlite3.connect('bank.db')
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_number = ?", (account,))
        result = cursor.fetchone()
        if result:
            if result[0] >= amount:
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE account_number = ?", (amount, account))
                cursor.execute("INSERT INTO transactions (account_number, amount, type) VALUES (?, ?, 'withdraw')", (account, amount))
                conn.commit()
                cursor.execute("SELECT balance FROM accounts WHERE account_number = ?", (account,))
                new_balance = cursor.fetchone()[0]
                conn.close()
                return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Withdrew £{amount:.2f} from {account}. New balance: £{new_balance:.2f}</p><a href='/'>Back</a>"
            conn.close()
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Insufficient funds in {account}</p><a href='/'>Back</a>"
        conn.close()
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Account {account} not found</p><a href='/'>Back</a>"
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

@app.route('/history', methods=['GET', 'POST'])
def history():
    if request.method == 'POST':
        account = request.form['account']
        conn = sqlite3.connect('bank.db')
        cursor = conn.cursor()
        cursor.execute("SELECT amount, type, timestamp FROM transactions WHERE account_number = ? ORDER BY timestamp DESC", (account,))
        transactions = cursor.fetchall()
        conn.close()
        if transactions:
            table = "<table><tr><th>Amount</th><th>Type</th><th>Time</th></tr>"
            for t in transactions:
                table += f"<tr><td>£{t[0]:.2f}</td><td>{t[1]}</td><td>{t[2]}</td></tr>"
            table += "</table>"
            return f"{BASE_STYLE}<h1>Test Bank - History</h1><p>Account {account}</p>{table}<a href='/'>Back</a>"
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>No transactions for {account}</p><a href='/'>Back</a>"
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
    conn = sqlite3.connect('bank.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM accounts WHERE account_number = ?", (account,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return jsonify({"account": account, "balance": result[0]}), 200
    return jsonify({"error": "Account not found"}), 404

@app.route('/api/history/<account>', methods=['GET'])
def api_history(account):
    conn = sqlite3.connect('bank.db')
    cursor = conn.cursor()
    cursor.execute("SELECT amount, type, timestamp FROM transactions WHERE account_number = ? ORDER BY timestamp DESC", (account,))
    transactions = cursor.fetchall()
    conn.close()
    if transactions:
        return jsonify([{"amount": t[0], "type": t[1], "timestamp": t[2]} for t in transactions]), 200
    return jsonify({"error": "No transactions found"}), 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('bank.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE username = ? AND password = ?", (username, password))
        result = cursor.fetchone()
        conn.close()
        if result:
            return f"{BASE_STYLE}<h1>Test Bank</h1><p class='success'>Welcome, {username}!</p><a href='/'>Back</a>"
        return f"{BASE_STYLE}<h1>Test Bank</h1><p class='error'>Invalid username or password</p><a href='/login'>Try again</a>"
    return f"""
        {BASE_STYLE}
        <h1>Test Bank - Login</h1>
        <form action="/login" method="POST">
            Username: <input type="text" name="username" required><br>
            Password: <input type="text" name="password" required><br>
            <input type="submit" value="Login">
        </form>
        <a href="/">Back</a>
    """

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
