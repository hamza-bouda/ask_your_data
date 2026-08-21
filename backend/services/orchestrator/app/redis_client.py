import redis.asyncio as redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Global Redis client pool
_redis_client = None

def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client

async def close_redis_client():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
