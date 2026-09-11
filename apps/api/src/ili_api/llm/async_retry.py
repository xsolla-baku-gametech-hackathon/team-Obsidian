import asyncio
import random
from typing import Callable, TypeVar, Any

T = TypeVar("T")

class MaxRetriesExceededError(Exception):
    """Raised when all retry attempts fail."""
    pass

async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    **kwargs: Any
) -> T:
    """Executes an async function with exponential backoff and jitter."""
    attempt = 0
    while attempt < retries:
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            attempt += 1
            if attempt >= retries:
                raise MaxRetriesExceededError(
                    f"Failed after {retries} attempts. Last error: {err}"
                ) from err
            
            # Exponential backoff: base_delay * 2^(attempt - 1)
            calculated_delay = base_delay * (2 ** (attempt - 1))
            # Add full jitter to prevent thundering herd
            jittered_delay = random.uniform(0, min(max_delay, calculated_delay))
            
            print(f"[Retry {attempt}/{retries}] Failed: {err}. Retrying in {jittered_delay:.2f}s...")
            await asyncio.sleep(jittered_delay)

    raise MaxRetriesExceededError("Execution unreachable.")