print("Starting worker script...")
import asyncio
import redis.asyncio as redis
import asyncpg
import json
import logging
import logging.handlers
import os

print("Imports completed")
pid = os.getpid()
log_file = f"/opt/banking-app/worker-{pid}.log"
handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=10*1024*1024, backupCount=5
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])
logger = logging.getLogger(__name__)
logger.info("Logger initialized")
print("Logging setup done")

async def init_db_pool():
    print("Initializing DB pool...")
    try:
        pool = await asyncpg.create_pool(
            database="test_bank",
            user="test_user",
            password="TestBank2025",
            host="localhost",
            min_size=1,
            max_size=24
        )
        logger.info("Database pool initialized")
        print("DB pool initialized")
        return pool
    except Exception as e:
        logger.error(f"Failed to initialize DB pool: {e}")
        print(f"DB pool failed: {e}")
        raise

async def process_transfer(pool, redis_client, transfer_data):
    transfer_id = transfer_data['transfer_id']
    from_account = transfer_data['from_account']
    to_account = transfer_data['to_account']
    amount = transfer_data['amount']

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                from_acc = await conn.fetchrow(
                    "SELECT balance FROM accounts WHERE account_number = $1 FOR UPDATE",
                    from_account
                )
                to_acc = await conn.fetchrow(
                    "SELECT balance FROM accounts WHERE account_number = $1",
                    to_account
                )

                if not from_acc or not to_acc:
                    await conn.execute(
                        "UPDATE transfer_jobs SET status = 'failed', result = $1 WHERE transfer_id = $2",
                        json.dumps({"error": "Account not found"}), transfer_id
                    )
                    logger.warning(f"Transfer {transfer_id} failed: Account not found")
                    return

                if from_acc['balance'] < amount:
                    await conn.execute(
                        "UPDATE transfer_jobs SET status = 'failed', result = $1 WHERE transfer_id = $2",
                        json.dumps({"error": "Insufficient funds"}), transfer_id
                    )
                    logger.warning(f"Transfer {transfer_id} failed: Insufficient funds")
                    return

                await conn.execute(
                    "UPDATE accounts SET balance = balance - $1 WHERE account_number = $2",
                    amount, from_account
                )
                await conn.execute(
                    "UPDATE accounts SET balance = balance + $1 WHERE account_number = $2",
                    amount, to_account
                )
                await conn.execute(
                    "UPDATE transfer_jobs SET status = 'completed', result = $1 WHERE transfer_id = $2",
                    json.dumps({"message": "Transfer successful"}), transfer_id
                )
                logger.info(f"Transfer {transfer_id} completed")
    except Exception as e:
        logger.error(f"Error processing transfer {transfer_id}: {e}")
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE transfer_jobs SET status = 'failed', result = $1 WHERE transfer_id = $2",
                json.dumps({"error": str(e)}), transfer_id
            )

async def main():
    print("Connecting to Redis...")
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    pool = await init_db_pool()
    try:
        await redis_client.ping()
        logger.info("Connected to Redis")
        print("Redis ping successful")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        print(f"Redis failed: {e}")
        return

    print("Entering worker loop...")
    while True:
        try:
            _, data = await redis_client.blpop('transfers')
            transfer = json.loads(data)
            await process_transfer(pool, redis_client, transfer)
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            print(f"Worker loop error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    print("Running asyncio...")
    asyncio.run(main())
