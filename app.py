from fastapi import FastAPI, HTTPException, Response, status, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import uuid
import asyncpg
import redis.asyncio as redis
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import BackgroundTasks

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

# Configuration for JWT (OAuth2)
SECRET_KEY = "your-secret-key"  # Replace with a secure key in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 for session handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Models for request/response validation
class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float

    @classmethod
    def validate(cls, v):
        if v.amount <= 0:
            raise ValueError("Amount must be positive")
        if len(v.from_account) != 6 or len(v.to_account) != 6:
            raise ValueError("Account numbers must be 6 characters")
        return v

class LoginRequest(BaseModel):
    username: str
    password: str

class AccountRequest(BaseModel):
    account_number: str
    balance: float

    @classmethod
    def validate(cls, v):
        if v.balance < 0:
            raise ValueError("Balance cannot be negative")
        if len(v.account_number) != 6:
            raise ValueError("Account number must be 6 characters")
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
            max_size=24
        )
        logger.info("Database pool initialized successfully")
        return pool
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {str(e)}")
        raise HTTPException(status_code=500, detail="Database initialization failed")

# JWT token creation
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Dependency to get current user from token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("Invalid token: No username in payload")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except JWTError as e:
        logger.warning(f"JWT error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

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

# HTML UI for root
@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Test Bank</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            p { font-size: 18px; }
            .container { max-width: 800px; margin: auto; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Welcome to Test Bank</h1>
            <p>Your friendly banking app is back online! Log in to access your account details.</p>
            <p><a href="/login">Click here to log in</a></p>
            <p>API endpoints available after login:</p>
            <ul>
                <li><a href="/api/balance/614437">Check Balance (614437)</a></li>
                <li><a href="/api/history/614437">View History (614437)</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Login UI
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Login - Test Bank</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .container { max-width: 400px; margin: auto; }
            form { display: flex; flex-direction: column; gap: 10px; }
            input { padding: 8px; font-size: 16px; }
            button { padding: 10px; background-color: #0066cc; color: white; border: none; cursor: pointer; }
            button:hover { background-color: #005bb5; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Login to Test Bank</h1>
            <form action="/login" method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Log In</button>
            </form>
            <p>Hint: Use "testuser" and "password123"</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == "testuser" and password == "password123":
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )
        logger.info(f"User {username} logged in successfully")
        # Redirect to root with token in query string (simpler for UI)
        return RedirectResponse(url=f"/?token={access_token}", status_code=303)
    logger.warning(f"Failed login attempt for user {username}")
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Login Failed - Test Bank</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .container { max-width: 400px; margin: auto; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Login Failed</h1>
            <p class="error">Invalid credentials. Please try again.</p>
            <p><a href="/login">Back to Login</a></p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=401)

# Other Endpoints
@app.post("/transfer")
async def transfer(request: TransferRequest, current_user: str = Depends(get_current_user)):
    try:
        TransferRequest.validate(request)
    except ValueError as e:
        logger.warning(f"Invalid transfer request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    transfer_id = str(uuid.uuid4())
    job_data = {
        'transfer_id': transfer_id,
        'from_account': request.from_account,
        'to_account': request.to_account,
        'amount': request.amount
    }
    try:
        async with app.state.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO transfer_jobs (transfer_id, from_account, to_account, amount, status, timestamp) VALUES ($1, $2, $3, $4, 'processing', CURRENT_TIMESTAMP)",
                transfer_id, request.from_account, request.to_account, request.amount
            )
    except Exception as e:
        logger.error(f"Failed to insert transfer job into DB: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to enqueue transfer")

    try:
        await app.state.redis.lpush('transfers', json.dumps(job_data))
        logger.info(f"Enqueued transfer: {transfer_id}")
    except Exception as e:
        logger.error(f"Failed to enqueue transfer to Redis: {str(e)}")
        async with app.state.db_pool.acquire() as conn:
            await conn.execute("DELETE FROM transfer_jobs WHERE transfer_id = $1", transfer_id)
        raise HTTPException(status_code=500, detail="Failed to enqueue transfer to Redis")

    return {"transfer_id": transfer_id}

@app.get("/transfer_status/{transfer_id}")
async def transfer_status(transfer_id: str, current_user: str = Depends(get_current_user)):
    try:
        async with app.state.db_pool.acquire() as conn:
            result = await conn.fetchrow("SELECT status, result FROM transfer_jobs WHERE transfer_id = $1", transfer_id)
            if not result:
                logger.warning(f"Transfer {transfer_id} not found")
                raise HTTPException(status_code=404, detail="Transfer not found")
            if result['status'] == 'processing':
                return Response(content=json.dumps({"status": "processing"}), status_code=202, media_type="application/json")
            return {"status": result['status'], "result": result['result'] if result['result'] else {}}
    except Exception as e:
        logger.error(f"Error fetching transfer status for {transfer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transfer status")

@app.get("/check")
async def check(account_number: str, current_user: str = Depends(get_current_user)):
    try:
        async with app.state.db_pool.acquire() as conn:
            account = await conn.fetchrow("SELECT balance FROM accounts WHERE account_number = $1", account_number)
            if not account:
                logger.warning(f"Account {account_number} not found")
                raise HTTPException(status_code=404, detail="Account not found")
            return {"account_number": account_number, "balance": float(account['balance'])}
    except Exception as e:
        logger.error(f"Error checking account {account_number}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check account")

@app.post("/open_account")
async def open_account(request: AccountRequest, current_user: str = Depends(get_current_user)):
    try:
        AccountRequest.validate(request)
    except ValueError as e:
        logger.warning(f"Invalid account request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    try:
        async with app.state.db_pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchrow("SELECT 1 FROM accounts WHERE account_number = $1", request.account_number)
                if existing:
                    logger.warning(f"Account {request.account_number} already exists")
                    raise HTTPException(status_code=400, detail="Account already exists")
                await conn.execute(
                    "INSERT INTO accounts (account_number, balance) VALUES ($1, $2)",
                    request.account_number, request.balance
                )
        logger.info(f"Opened account: {request.account_number} with balance £{request.balance:.2f}")
        return {"message": f"Account {request.account_number} opened with balance £{request.balance:.2f}"}
    except Exception as e:
        logger.error(f"Error opening account {request.account_number}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to open account")

@app.get("/list", response_model=List[Account])
async def list_accounts(current_user: str = Depends(get_current_user)):
    try:
        async with app.state.db_pool.acquire() as conn:
            accounts = await conn.fetch("SELECT account_number, balance FROM accounts")
        return [{"account_number": acc['account_number'], "balance": float(acc['balance'])} for acc in accounts]
    except Exception as e:
        logger.error(f"Error listing accounts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list accounts")

@app.get("/api")
async def api(current_user: str = Depends(get_current_user)):
    return {"message": "API endpoint - future implementation"}

@app.get("/history", response_model=List[Transfer])
async def history(account_number: str, current_user: str = Depends(get_current_user)):
    try:
        async with app.state.db_pool.acquire() as conn:
            transfers = await conn.fetch(
                "SELECT transfer_id, from_account, to_account, amount, status, result FROM transfer_jobs WHERE from_account = $1 OR to_account = $1",
                account_number
            )
        return [
            {
                "transfer_id": t['transfer_id'],
                "from_account": t['from_account'],
                "to_account": t['to_account'],
                "amount": float(t['amount']),
                "status": t['status'],
                "result": t['result'] if t['result'] else None
            } for t in transfers
        ]
    except Exception as e:
        logger.error(f"Error fetching history for account {account_number}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")

@app.post("/withdraw")
async def withdraw(request: WithdrawRequest, current_user: str = Depends(get_current_user)):
    try:
        WithdrawRequest.validate(request)
    except ValueError as e:
        logger.warning(f"Invalid withdraw request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    try:
        async with app.state.db_pool.acquire() as conn:
            async with conn.transaction():
                account = await conn.fetchrow("SELECT balance FROM accounts WHERE account_number = $1 FOR UPDATE", request.account_number)
                if not account:
                    logger.warning(f"Account {request.account_number} not found")
                    raise HTTPException(status_code=404, detail="Account not found")
                balance = account['balance']
                if balance < request.amount:
                    logger.warning(f"Insufficient funds in account {request.account_number}: balance £{balance:.2f}, requested £{request.amount:.2f}")
                    raise HTTPException(status_code=400, detail="Insufficient funds")
                await conn.execute("UPDATE accounts SET balance = balance - $1 WHERE account_number = $2", request.amount, request.account_number)
        logger.info(f"Withdrew £{request.amount:.2f} from account {request.account_number}")
        return {"message": f"Withdrew £{request.amount:.2f} from account {request.account_number}"}
    except Exception as e:
        logger.error(f"Error withdrawing from account {request.account_number}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to withdraw")

@app.post("/register")
async def register(request: RegisterRequest):
    try:
        async with app.state.db_pool.acquire() as conn:
            logger.info(f"User {request.username} registered - future implementation")
            return {"message": f"User {request.username} registered - future implementation"}
    except Exception as e:
        logger.error(f"Error registering user {request.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to register user")

@app.get("/api/balance/{account_number}")
async def api_balance(account_number: str, current_user: str = Depends(get_current_user)):
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

@app.get("/api/history/{account_number}")
async def api_history(account_number: str, current_user: str = Depends(get_current_user)):
    try:
        async with app.state.db_pool.acquire() as conn:
            transfers = await conn.fetch(
                "SELECT transfer_id, from_account, to_account, amount, status, result FROM transfer_jobs WHERE from_account = $1 OR to_account = $1",
                account_number
            )
        return [
            {
                "transfer_id": t['transfer_id'],
                "from_account": t['from_account'],
                "to_account": t['to_account'],
                "amount": float(t['amount']),
                "status": t['status'],
                "result": t['result'] if t['result'] else None
            } for t in transfers
        ]
    except Exception as e:
        logger.error(f"Error fetching history for {account_number}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")
