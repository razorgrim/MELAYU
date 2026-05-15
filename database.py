import os
import aiomysql
from dotenv import load_dotenv

load_dotenv()

pool = None

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME"),
    "autocommit": True
}

async def connect_db():
    global pool

    pool = await aiomysql.create_pool(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_NAME"),
        autocommit=True,
        minsize=1,
        maxsize=10
    )

    print("[DATABASE] Connected to MySQL")


async def get_pool():
    return pool


async def execute(query, params=None):
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)


async def fetchone(query, params=None):
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, params)
            return await cur.fetchone()


async def fetchall(query, params=None):
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, params)
            return await cur.fetchall()