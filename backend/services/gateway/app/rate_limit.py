import time
from typing import AsyncGenerator
import redis.asyncio as redis
from fastapi import HTTPException

try:
    from app.config import REDIS_URL, RATE_LIMIT_PER_MINUTE
except ImportError:
    from backend.services.gateway.app.config import REDIS_URL, RATE_LIMIT_PER_MINUTE


# Global Redis client
_redis_client: redis.Redis | None = None

async def init_redis() -> None:
    """Initialize the global Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def close_redis() -> None:
    """Close the global Redis client."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None

def get_redis() -> redis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return _redis_client

async def check_rate_limit(user_id: str, action: str = "chat", tenant_id: str | None = None) -> None:
    """Check if the given user/tenant has exceeded the rate limit.
    
    Uses a simple sliding window approach stored in Redis.
    Raises HTTPException 429 if the limit is exceeded.
    """
    client = get_redis()
    now = int(time.time())
    
    # Standard per-minute rate limit for chat and generic actions
    if action == "chat":
        window_start = now - 60
        key = f"rate_limit:{action}:{user_id}"
        limit = RATE_LIMIT_PER_MINUTE
        expiry = 60
    elif action == "run" and tenant_id:
        # Daily limit per tenant for runs
        window_start = now - 86400
        key = f"rate_limit:{action}:{tenant_id}"
        limit = 500
        expiry = 86400
    elif action == "export":
        # Daily limit per user for exports
        window_start = now - 86400
        key = f"rate_limit:{action}:{user_id}"
        limit = 20
        expiry = 86400
    elif action == "sync" and tenant_id:
        # Daily limit per tenant for syncs
        window_start = now - 86400
        key = f"rate_limit:{action}:{tenant_id}"
        limit = 10
        expiry = 86400
    else:
        window_start = now - 60
        key = f"rate_limit:default:{user_id}"
        limit = 60
        expiry = 60
    
    # Use a Redis pipeline for atomic execution
    async with client.pipeline(transaction=True) as pipe:
        # Remove timestamps older than the window
        pipe.zremrangebyscore(key, "-inf", window_start)
        # Add the current request
        pipe.zadd(key, {str(now): now})
        # Count the requests in the window
        pipe.zcard(key)
        # Set expiry on the key to avoid memory leaks
        pipe.expire(key, expiry)
        
        results = await pipe.execute()
        
    request_count = results[2]
    
    if request_count > limit:
        period = "minute" if expiry <= 60 else "day"
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {limit} requests per {period}."
        )
