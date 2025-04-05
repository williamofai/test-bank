from fastapi import FastAPI, HTTPException, Response, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional, Union
import uuid
import asyncpg
import redis.asyncio as redis
import json
import logging
import bcrypt
import asyncio
import random

# Setup logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/opt/banking-app/fastapi.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# Mount static files directory for CSS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Models for request/response validation
class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float

    @classmethod
    def validate(cls, v):
        if v.amount <= 0:
            raise ValueError("Amount must be positive")
        if len(v.to_account) != 6:
            raise ValueError("To account number must be 6 characters")
        if len(v.from_account) > 50:
            raise ValueError("From account identifier must not exceed 50 characters")
        return v

class DepositRequest(BaseModel):
    account_number: str
    amount: float

    @classmethod
    def validate(cls, v):
        if v.amount <= 0:
            raise ValueError("Amount must be positive")
        if len(v.account_number) != 6:
            raise ValueError("Account number must be 6 characters")
        return v

class LoginRequest(BaseModel):
    username: str
    password: str

class AccountRequest(BaseModel):
    account_number: str
    balance: float
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[str] = None
    address_line_one: Optional[str] = None
    address_line_two: Optional[str] = None
    town: Optional[str] = None
    city: Optional[str] = None
    post_code: Optional[str] = None

    @classmethod
    def validate(cls, v):
        if v.balance < 0:
            raise ValueError("Balance cannot be negative")
        if len(v.account_number) != 6:
            raise ValueError("Account number must be 6 characters")
        return v

class BulkAccountRequest(BaseModel):
    accounts: List[AccountRequest]

    @classmethod
    def validate(cls, v):
        for account in v.accounts:
            if account.balance < 0:
                raise ValueError(f"Balance cannot be negative for account {account.account_number}")
            if len(account.account_number) != 6:
                raise ValueError(f"Account number must be 6 characters for account {account.account_number}")
        return v

class WithdrawRequest(BaseModel):
    account_number: str
    amount: float

    @classmethod
    def validate(cls, v):
        if v.amount <= 0:
            raise ValueError("Amount must be positive")
        if len(v.account_number) != 6:
            raise ValueError("Account number must be 6 characters")
        return v

class DepositRequest(BaseModel):
    account_number: str
    amount: float

    @classmethod
    def validate(cls, v):
        if v.amount <= 0:
            raise ValueError("Amount must be positive")
        if len(v.account_number) != 6:
            raise ValueError("Account number must be 6 characters")
        return v

class RegisterRequest(BaseModel):
    username: str
    password: str

class Account(BaseModel):
    account_number: str
    balance: float

class Transfer(BaseModel):
    transfer_id: str
    from_account: str
    to_account: str
    amount: float
    status: str
    result: Optional[Dict] = None

# Database pool initialization
async def init_db():
    try:
        pool = await asyncpg.create_pool(
            database="test_bank",
            user="test_user",
            password="TestBank2025",
            host="localhost",
            min_size=1,
            max_size=25
        )
        logger.info("Database pool initialized successfully")
        return pool
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {str(e)}")
        raise HTTPException(status_code=500, detail="Database initialization failed")

# Initialize app with DB and Redis
@app.on_event("startup")
async def startup():
    app.state.db_pool = await init_db()
    try:
        app.state.redis = redis.Redis(host='localhost', port=6379, db=0)
        await app.state.redis.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise HTTPException(status_code=500, detail="Redis initialization failed")

@app.on_event("shutdown")
async def shutdown():
    try:
        await app.state.db_pool.close()
        logger.info("Database pool closed")
    except Exception as e:
        logger.error(f"Error closing database pool: {str(e)}")
    try:
        await app.state.redis.close()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {str(e)}")

# Helper function to render navigation bar
def render_nav(username: str = "", current_path: str = "/"):
    nav_items = [
        ("Home", "/"),
        ("Login", "/login"),
        ("Register", "/register")
    ] if not username else [
        ("Home", "/"),
        ("Dashboard", f"/dashboard?username={username}"),
        ("Check Balance", f"/check-balance?username={username}"),
        ("View History", f"/view-history?username={username}"),
        ("Deposit", f"/deposit?username={username}"),
        ("Logout", "/logout")
    ]
    nav_html = "<ul>"
    for name, url in nav_items:
        active_class = "active" if current_path == url.split("?")[0] else ""
        nav_html += f'<li><a href="{url}" class="{active_class}">{name}</a></li>'
    nav_html += "</ul>"
    return nav_html

# Helper function to render base HTML structure
def render_base_html(title: str, content: str, username: str = "", current_path: str = "/"):
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Test Bank</title>
        <link rel="stylesheet" href="/static/styles.css">
        <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
    </head>
    <body>
        <div class="header">
            <img src="/static/logo.png" alt="Test Bank Logo">
            <h1>Test Bank</h1>
        </div>
        <div class="nav">
            {render_nav(username, current_path)}
        </div>
        <div class="container">
            {content}
        </div>
    </body>
    </html>
    """

# HTML UI for root (welcome page with login link)
@app.get("/", response_class=HTMLResponse)
async def root(username: str = ""):
    if username:
        return RedirectResponse(url=f"/dashboard?username={username}", status_code=303)
    content = """
    <h1>Welcome to Test Bank</h1>
    <p>Your trusted banking partner in the UK. Log in or register to manage your accounts securely.</p>
    <a href="/login" class="button">Log In</a>
    <a href="/register" class="button">Register</a>
    """
    return HTMLResponse(content=render_base_html("Welcome", content, current_path="/"))

# Dashboard UI
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(username: str, message: str = None):
    logger.info(f"Dashboard: Received username={username}")
    if not username:
        logger.warning("Dashboard: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    message_html = f'<p class="success-message">{message}</p>' if message else ''
    content = f"""
    <h1>Welcome, {username}!</h1>
    {message_html}
    <p>You're logged in. Select an option below:</p>
    <a href="/check-balance?username={username}" class="button">Check Balance</a>
    <a href="/view-history?username={username}" class="button">View History</a>
    <a href="/deposit?username={username}" class="button">Deposit</a>
    <a href="/logout" class="button">Logout</a>
    """
    return HTMLResponse(content=render_base_html("Dashboard", content, username, "/dashboard"))

# Login UI
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    content = """
    <h1>Login to Test Bank</h1>
    <form action="/login" method="post">
        <label for="username">Username:</label>
        <input type="text" id="username" name="username" placeholder="Enter username" required>
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" placeholder="Enter password" required>
        <button type="submit">Log In</button>
    </form>
    <p>Don't have an account? <a href="/register">Register</a></p>
    """
    return HTMLResponse(content=render_base_html("Login", content, current_path="/login"))

@app.post("/login", response_class=HTMLResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    try:
        async with app.state.db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT username, password_hash FROM users WHERE username = $1",
                username
            )
            if not user:
                logger.warning(f"Login failed: Username {username} not found")
                content = """
                <h1>Login Failed</h1>
                <p class="error-message">Invalid username or password. Please try again.</p>
                <a href="/login" class="button">Back to Login</a>
                """
                return HTMLResponse(content=render_base_html("Login Failed", content, current_path="/login"), status_code=401)

            stored_hash = user['password_hash'].encode('utf-8')
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                logger.warning(f"Login failed: Incorrect password for user {username}")
                content = """
                <h1>Login Failed</h1>
                <p class="error-message">Invalid username or password. Please try again.</p>
                <a href="/login" class="button">Back to Login</a>
                """
                return HTMLResponse(content=render_base_html("Login Failed", content, current_path="/login"), status_code=401)

            logger.info(f"User {username} logged in successfully")
            return RedirectResponse(url=f"/dashboard?username={username}", status_code=303)
    except Exception as e:
        logger.error(f"Error during login for user {username}: {str(e)}")
        content = """
        <h1>Login Error</h1>
        <p class="error-message">An error occurred during login. Please try again later.</p>
        <a href="/login" class="button">Back to Login</a>
        """
        return HTMLResponse(content=render_base_html("Login Error", content, current_path="/login"), status_code=500)

# Register UI
@app.get("/register", response_class=HTMLResponse)
async def register_page():
    content = """
    <h1>Register for Test Bank</h1>
    <form action="/register" method="post">
        <label for="username">Username:</label>
        <input type="text" id="username" name="username" placeholder="Enter username" required>
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" placeholder="Enter password" required>
        <button type="submit">Register</button>
    </form>
    <p>Already have an account? <a href="/login">Log In</a></p>
    """
    return HTMLResponse(content=render_base_html("Register", content, current_path="/register"))

# Logout endpoint
@app.get("/logout", response_class=HTMLResponse)
async def logout(response: Response):
    logger.info("User logged out")
    response.delete_cookie("access_token")
    return RedirectResponse(url="/", status_code=303)

# Check Balance UI
@app.get("/check-balance", response_class=HTMLResponse)
async def check_balance_page(username: str):
    logger.info(f"Check-balance: Received username={username}")
    if not username:
        logger.warning("Check-balance: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    content = """
    <h1>Check Balance</h1>
    <form action="/check-balance" method="post">
        <input type="hidden" name="username" value="{username}">
        <label for="account_number">Account Number:</label>
        <input type="text" id="account_number" name="account_number" placeholder="e.g., 614437" required>
        <button type="submit">Submit</button>
    </form>
    <a href="/dashboard?username={username}" class="button">Back to Dashboard</a>
    """.format(username=username)
    return HTMLResponse(content=render_base_html("Check Balance", content, username, "/check-balance"))

@app.post("/check-balance", response_class=HTMLResponse)
async def check_balance_submit(account_number: str = Form(...), username: str = Form(...)):
    logger.info(f"Check-balance POST: Received username={username}")
    if not username:
        logger.warning("Check-balance POST: No username provided")
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url=f"/balance/{account_number}?username={username}", status_code=303)

# View History UI
@app.get("/view-history", response_class=HTMLResponse)
async def view_history_page(username: str):
    logger.info(f"View-history: Received username={username}")
    if not username:
        logger.warning("View-history: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    content = """
    <h1>View History</h1>
    <form action="/view-history" method="post">
        <input type="hidden" name="username" value="{username}">
        <label for="account_number">Account Number:</label>
        <input type="text" id="account_number" name="account_number" placeholder="e.g., 614437" required>
        <button type="submit">Submit</button>
    </form>
    <a href="/dashboard?username={username}" class="button">Back to Dashboard</a>
    """.format(username=username)
    return HTMLResponse(content=render_base_html("View History", content, username, "/view-history"))

@app.post("/view-history", response_class=HTMLResponse)
async def view_history_submit(account_number: str = Form(...), username: str = Form(...)):
    logger.info(f"View-history POST: Received username={username}")
    if not username:
        logger.warning("View-history POST: No username provided")
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url=f"/history/{account_number}?username={username}", status_code=303)

# Balance UI
@app.get("/balance/{account_number}", response_class=HTMLResponse)
async def balance_page(account_number: str, username: str):
    logger.info(f"Balance: Received username={username}")
    if not username:
        logger.warning("Balance: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    try:
        async with app.state.db_pool.acquire() as conn:
            account = await conn.fetchrow(
                "SELECT account_number, balance, first_name, last_name, dob, address_line_one, address_line_two, town, city, post_code FROM accounts WHERE account_number = $1",
                account_number
            )
            if not account:
                logger.warning(f"Account {account_number} not found")
                content = """
                <h1>Account Not Found</h1>
                <p>The account number you entered was not found.</p>
                <a href="/check-balance?username={username}" class="button">Back to Check Balance</a>
                """.format(username=username)
                return HTMLResponse(content=render_base_html("Account Not Found", content, username, "/check-balance"), status_code=404)

        content = f"""
        <h1>Account Details</h1>
        <table>
            <tr><th>Account Number</th><td>{account['account_number']}</td></tr>
            <tr><th>Balance</th><td>£{account['balance']:.2f}</td></tr>
            <tr><th>First Name</th><td>{account['first_name'] or 'N/A'}</td></tr>
            <tr><th>Last Name</th><td>{account['last_name'] or 'N/A'}</td></tr>
            <tr><th>Date of Birth</th><td>{account['dob'] or 'N/A'}</td></tr>
            <tr><th>Address Line 1</th><td>{account['address_line_one'] or 'N/A'}</td></tr>
            <tr><th>Address Line 2</th><td>{account['address_line_two'] or 'N/A'}</td></tr>
            <tr><th>Town</th><td>{account['town'] or 'N/A'}</td></tr>
            <tr><th>City</th><td>{account['city'] or 'N/A'}</td></tr>
            <tr><th>Postcode</th><td>{account['post_code'] or 'N/A'}</td></tr>
        </table>
        <a href="/check-balance?username={username}" class="button">Back to Check Balance</a>
        """
        return HTMLResponse(content=render_base_html("Account Details", content, username, "/balance"))
    except Exception as e:
        logger.error(f"Error fetching balance for {account_number}: {str(e)}")
        content = """
        <h1>Error</h1>
        <p>Failed to fetch account details. Please try again later.</p>
        <a href="/check-balance?username={username}" class="button">Back to Check Balance</a>
        """.format(username=username)
        return HTMLResponse(content=render_base_html("Error", content, username, "/check-balance"), status_code=500)

# History UI
@app.get("/history/{account_number}", response_class=HTMLResponse)
async def history_page(account_number: str, username: str):
    logger.info(f"History: Received username={username}")
    if not username:
        logger.warning("History: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    try:
        async with app.state.db_pool.acquire() as conn:
            transfers = await conn.fetch(
                "SELECT transfer_id, from_account, to_account, amount, status, result FROM transfer_jobs WHERE from_account = $1 OR to_account = $1",
                account_number
            )
            if not transfers:
                content = f"""
                <h1>Transfer History for {account_number}</h1>
                <p>No transfers found for this account.</p>
                <a href="/view-history?username={username}" class="button">Back to View History</a>
                """
                return HTMLResponse(content=render_base_html("Transfer History", content, username, "/view-history"))

        table_rows = ""
        for t in transfers:
            result = t['result'] if t['result'] else {}
            result_message = result.get('message', 'N/A') if isinstance(result, dict) else 'N/A'
            table_rows += f"""
            <tr>
                <td>{t['transfer_id']}</td>
                <td>{t['from_account']}</td>
                <td>{t['to_account']}</td>
                <td>£{t['amount']:.2f}</td>
                <td>{t['status']}</td>
                <td>{result_message}</td>
            </tr>
            """

        content = f"""
        <h1>Transfer History for {account_number}</h1>
        <table>
            <tr>
                <th>Transfer ID</th>
                <th>From Account</th>
                <th>To Account</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Result</th>
            </tr>
            {table_rows}
        </table>
        <a href="/view-history?username={username}" class="button">Back to View History</a>
        """
        return HTMLResponse(content=render_base_html("Transfer History", content, username, "/history"))
    except Exception as e:
        logger.error(f"Error fetching history for {account_number}: {str(e)}")
        content = """
        <h1>Error</h1>
        <p>Failed to fetch transfer history. Please try again later.</p>
        <a href="/view-history?username={username}" class="button">Back to View History</a>
        """.format(username=username)
        return HTMLResponse(content=render_base_html("Error", content, username, "/view-history"), status_code=500)

# Deposit UI (GET endpoint to render the form)
@app.get("/deposit", response_class=HTMLResponse)
async def deposit_page(username: str, error_message: str = None):
    logger.info(f"Deposit GET: Received username={username}")
    if not username:
        logger.warning("Deposit GET: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    error_html = f'<p class="error-message">{error_message}</p>' if error_message else ''
    content = f"""
    <h1>Deposit Money</h1>
    {error_html}
    <form action="/deposit" method="post">
        <input type="hidden" name="username" value="{username}">
        <label for="account_number">Account Number:</label>
        <input type="text" id="account_number" name="account_number" placeholder="e.g., 614437" required>
        <label for="amount">Amount (£):</label>
        <input type="number" id="amount" name="amount" step="0.01" min="0" placeholder="e.g., 100.00" required>
        <button type="submit">Deposit</button>
    </form>
    <a href="/dashboard?username={username}" class="button">Back to Dashboard</a>
    """
    return HTMLResponse(content=render_base_html("Deposit", content, username, "/deposit"))

# Deposit UI (POST endpoint to handle form submission)
@app.post("/deposit", response_class=HTMLResponse)
async def deposit(account_number: str = Form(...), amount: float = Form(...), username: str = Form(...)):
    logger.info(f"Deposit POST: Received username={username}, account_number={account_number}, amount={amount}")
    if not username:
        logger.warning("Deposit POST: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    # Validate the deposit request using DepositRequest
    try:
        deposit_request = DepositRequest(account_number=account_number, amount=amount)
        DepositRequest.validate(deposit_request)
    except ValueError as e:
        logger.warning(f"Invalid deposit request: {str(e)}")
        return RedirectResponse(url=f"/deposit?username={username}&error_message={str(e)}", status_code=303)

    try:
        async with app.state.db_pool.acquire() as conn:
            async with conn.transaction():
                account = await conn.fetchrow("SELECT balance FROM accounts WHERE account_number = $1 FOR UPDATE", account_number)
                if not account:
                    logger.warning(f"Account {account_number} not found")
                    return RedirectResponse(url=f"/deposit?username={username}&error_message=Account not found", status_code=303)
                # Update the account balance
                await conn.execute("UPDATE accounts SET balance = balance + $1 WHERE account_number = $2", amount, account_number)
                # Log the deposit in transfer_jobs
                transfer_id = str(uuid.uuid4())
                result = {"message": f"Deposited £{amount:.2f} to account {account_number}"}
                result_json = json.dumps(result)
                await conn.execute(
                    "INSERT INTO transfer_jobs (transfer_id, from_account, to_account, amount, status, result, timestamp) VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)",
                    transfer_id, "EXTERNAL_DEPOSIT", account_number, amount, "deposit", result_json
                )
        logger.info(f"Deposited £{amount:.2f} to account {account_number}")
        return RedirectResponse(url=f"/dashboard?username={username}&message=Successfully deposited £{amount:.2f} to account {account_number}", status_code=303)
    except Exception as e:
        logger.error(f"Error depositing to account {account_number}: {str(e)}")
        return RedirectResponse(url=f"/deposit?username={username}&error_message=Failed to deposit. Please try again later.", status_code=303)

@app.post("/open_account")
async def open_account(request: Union[AccountRequest, BulkAccountRequest], username: str = ""):
    logger.info(f"Open-account: Received username={username}")
    if not username:
        logger.warning("Open-account: No username provided")
        raise HTTPException(status_code=401, detail="Not authenticated")

    accounts_to_create = []
    if isinstance(request, BulkAccountRequest):
        try:
            BulkAccountRequest.validate(request)
            accounts_to_create = request.accounts
        except ValueError as e:
            logger.warning(f"Invalid bulk account request: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
    else:
        try:
            AccountRequest.validate(request)
            accounts_to_create = [request]
        except ValueError as e:
            logger.warning(f"Invalid account request: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    try:
        async with app.state.db_pool.acquire() as conn:
            async with conn.transaction():
                existing_accounts = await conn.fetch(
                    "SELECT account_number FROM accounts WHERE account_number = ANY($1)",
                    [acc.account_number for acc in accounts_to_create]
                )
                existing_set = {row['account_number'] for row in existing_accounts}
                if existing_set:
                    logger.warning(f"Accounts already exist: {existing_set}")
                    raise HTTPException(status_code=400, detail=f"Accounts already exist: {existing_set}")

                await conn.executemany(
                    """
                    INSERT INTO accounts (
                        account_number, balance, first_name, last_name, dob, 
                        address_line_one, address_line_two, town, city, post_code
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    [
                        (
                            acc.account_number,
                            acc.balance,
                            acc.first_name,
                            acc.last_name,
                            acc.dob,
                            acc.address_line_one,
                            acc.address_line_two,
                            acc.town,
                            acc.city,
                            acc.post_code
                        )
                        for acc in accounts_to_create if acc.account_number not in existing_set
                    ]
                )
        created_count = len(accounts_to_create)
        logger.info(f"Opened {created_count} accounts")
        return {"message": f"Opened {created_count} accounts successfully"}
    except Exception as e:
        logger.error(f"Error opening accounts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to open accounts")

@app.get("/list", response_model=List[Account])
async def list_accounts(username: str = ""):
    logger.info(f"List-accounts: Received username={username}")
    if not username:
        logger.warning("List-accounts: No username provided")
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        async with app.state.db_pool.acquire() as conn:
            accounts = await conn.fetch("SELECT account_number, balance FROM accounts")
        return [{"account_number": acc['account_number'], "balance": float(acc['balance'])} for acc in accounts]
    except Exception as e:
        logger.error(f"Error listing accounts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list accounts")

@app.get("/api")
async def api(username: str = ""):
    logger.info(f"API: Received username={username}")
    if not username:
        logger.warning("API: No username provided")
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"message": "API endpoint - future implementation"}

@app.get("/api/balance/{account_number}")
async def api_balance(account_number: str, username: str = ""):
    logger.info(f"API-balance: Received username={username}")
    if not username:
        logger.warning("API-balance: No username provided")
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        async with app.state.db_pool.acquire() as conn:
            account = await conn.fetchrow("SELECT balance FROM accounts WHERE account_number = $1", account_number)
            if not account:
                logger.warning(f"Account {account_number} not found")
                raise HTTPException(status_code=404, detail="Account not found")
            return {"account": account_number, "balance": float(account['balance'])}
    except Exception as e:
        logger.error(f"Error fetching balance for {account_number}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch balance")

@app.get("/history/{account_number}", response_class=HTMLResponse)
async def history_page(account_number: str, username: str):
    logger.info(f"History: Received username={username}")
    if not username:
        logger.warning("History: No username provided")
        return RedirectResponse(url="/login", status_code=303)

    try:
        async with app.state.db_pool.acquire() as conn:
            transfers = await conn.fetch(
                "SELECT transfer_id, from_account, to_account, amount, status, result FROM transfer_jobs WHERE from_account = $1 OR to_account = $1",
                account_number
            )
            if not transfers:
                content = f"""
                <h1>Transfer History for {account_number}</h1>
                <p>No transfers found for this account.</p>
                <a href="/view-history?username={username}" class="button">Back to View History</a>
                """
                return HTMLResponse(content=render_base_html("Transfer History", content, username, "/view-history"))

        table_rows = ""
        for t in transfers:
            # Parse the result JSON string into a dictionary
            result = json.loads(t['result']) if t['result'] else {}
            result_message = result.get('message', 'N/A') if isinstance(result, dict) else 'N/A'
            table_rows += f"""
            <tr>
                <td>{t['transfer_id']}</td>
                <td>{t['from_account']}</td>
                <td>{t['to_account']}</td>
                <td>£{t['amount']:.2f}</td>
                <td>{t['status']}</td>
                <td>{result_message}</td>
            </tr>
            """

        content = f"""
        <h1>Transfer History for {account_number}</h1>
        <table>
            <tr>
                <th>Transfer ID</th>
                <th>From Account</th>
                <th>To Account</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Result</th>
            </tr>
            {table_rows}
        </table>
        <a href="/view-history?username={username}" class="button">Back to View History</a>
        """
        return HTMLResponse(content=render_base_html("Transfer History", content, username, "/history"))
    except Exception as e:
        logger.error(f"Error fetching history for {account_number}: {str(e)}")
        content = """
        <h1>Error</h1>
        <p>Failed to fetch transfer history. Please try again later.</p>
        <a href="/view-history?username={username}" class="button">Back to View History</a>
        """.format(username=username)
        return HTMLResponse(content=render_base_html("Error", content, username, "/view-history"), status_code=500)

@app.post("/register")
async def register(request: Request, username: str = Form(None), password: str = Form(None)):
    if username and password:
        try:
            register_request = RegisterRequest(username=username, password=password)
            is_form_submission = True
        except ValueError as e:
            logger.warning(f"Invalid form data: {str(e)}")
            content = f"""
            <h1>Registration Failed</h1>
            <p class="error-message">Invalid form data: {str(e)}</p>
            <a href="/register" class="button">Try Again</a>
            """
            return HTMLResponse(content=render_base_html("Registration Failed", content, current_path="/register"), status_code=400)
    else:
        try:
            body = await request.json()
            register_request = RegisterRequest(**body)
            is_form_submission = False
        except ValueError as e:
            logger.warning(f"Invalid JSON data: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
        except Exception as e:
            logger.warning(f"Failed to parse JSON request: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid request format")

    async with app.state.db_pool.acquire() as conn:
        existing_user = await conn.fetchrow(
            "SELECT username FROM users WHERE username = $1",
            register_request.username
        )
        if existing_user:
            logger.warning(f"Registration failed: Username {register_request.username} already exists")
            if is_form_submission:
                content = f"""
                <h1>Registration Failed</h1>
                <p class="error-message">Username {register_request.username} already exists.</p>
                <a href="/register" class="button">Try Again</a>
                """
                return HTMLResponse(content=render_base_html("Registration Failed", content, current_path="/register"), status_code=400)
            raise HTTPException(status_code=400, detail=f"Username {register_request.username} already exists")

        try:
            password_hash = bcrypt.hashpw(register_request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error hashing password for user {register_request.username}: {str(e)}")
            if is_form_submission:
                content = """
                <h1>Error</h1>
                <p class="error-message">Failed to hash password. Please try again later.</p>
                <a href="/register" class="button">Try Again</a>
                """
                return HTMLResponse(content=render_base_html("Error", content, current_path="/register"), status_code=500)
            raise HTTPException(status_code=500, detail="Failed to hash password")

        try:
            await conn.execute(
                "INSERT INTO users (username, password_hash) VALUES ($1, $2)",
                register_request.username, password_hash
            )
            logger.info(f"User {register_request.username} registered successfully")
            if is_form_submission:
                return RedirectResponse(url="/login", status_code=303)
            return JSONResponse(content={"message": f"User {register_request.username} registered successfully"})
        except Exception as e:
            logger.error(f"Error inserting user {register_request.username} into database: {str(e)}")
            if is_form_submission:
                content = """
                <h1>Error</h1>
                <p class="error-message">Failed to register user. Please try again later.</p>
                <a href="/register" class="button">Try Again</a>
                """
                return HTMLResponse(content=render_base_html("Error", content, current_path="/register"), status_code=500)
            raise HTTPException(status_code=500, detail="Failed to register user")
