from __future__ import annotations

import asyncio
import datetime
import functools
import hashlib
import json
import pickle
import random
import time
from collections.abc import Awaitable, Callable
from functools import cache
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from loguru import logger
from pydantic import BaseModel

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")


def retry(
    retries: int = 10,
    delay: float = 5.0,
    exponential_backoff: bool = False,
    on_exception: Callable[[Exception], bool | None] | None = None,
):
    """Retry a function up to 'retries' times, with a delay of 'delay' seconds.
    If 'exponential_backoff' is True, the delay will double each time,
    exponentially increasing."""

    if on_exception is None:
        on_exception = lambda _: True

    def on_exception_wrapper(func, i: int, e: Exception):
        logger.error(f"Retrying {func.__name__}; {i + 1} / {retries} : {e}")

        if on_exception(e) is False:
            logger.error(e)
            raise e

        return True

    def calc_sleep_time(i: int) -> float:
        sleep = random.uniform(0, delay)
        sleep += delay if not exponential_backoff else delay * 2**i
        return sleep

    def inner(func: Callable[P, T] | Callable[P, Awaitable[T]]) -> Callable[P, T] | Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            e = Exception()
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)  # type: ignore
                except Exception as t_e:
                    e = t_e
                    on_exception_wrapper(func=func, i=i, e=e)

                await asyncio.sleep(calc_sleep_time(i))
            raise e  # type: ignore

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            e = Exception()
            for i in range(retries):
                try:
                    return func(*args, **kwargs)  # type: ignore
                except Exception as t_e:
                    e = t_e
                    on_exception_wrapper(func=func, i=i, e=e)

                time.sleep(calc_sleep_time(i))
            raise e  # type: ignore

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return inner


@cache
def get_cache_dir() -> Path:
    filepath = str(Path(__file__).absolute()).encode()

    h = hashlib.sha1(filepath).hexdigest()

    cache_dir = Path("/tmp/") / h

    cache_dir.mkdir(exist_ok=True)

    return cache_dir


def normalize_for_hash(obj: Any) -> Any:
    """Normalize data structures for consistent hashing."""
    if isinstance(obj, list | tuple):
        return [normalize_for_hash(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(key): normalize_for_hash(value) for key, value in sorted(obj.items(), key=lambda x: str(x[0]))}
    elif isinstance(obj, set | frozenset):
        return sorted(normalize_for_hash(item) for item in obj)
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, datetime.timedelta):
        return obj.total_seconds()
    elif isinstance(obj, Path):
        return str(obj.absolute())
    elif isinstance(obj, BaseModel):
        return obj.model_dump_json()
    elif hasattr(obj, "__dict__"):
        # Handle custom objects by converting their __dict__ to a sorted dict
        return normalize_for_hash(obj.__dict__)
    return obj


def consistent_hash(obj: Any) -> str:
    """Create a consistent hash for any supported Python object."""
    try:
        normalized = normalize_for_hash(obj)
        # Use dumps with sort_keys=True for consistent ordering
        json_str = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()
    except (TypeError, ValueError) as e:
        raise ValueError(f"Unable to hash object: {e}")


def get_cached_result(
    func_name: str,
    args: tuple,
    kwargs: dict,
    stale_interval: datetime.timedelta | None = None,
) -> tuple[bool, Any | None]:
    """
    Core caching logic to retrieve cached results.

    Args:
        func_name: Name of the function being cached
        args: Function arguments
        kwargs: Function keyword arguments
        stale_interval: Optional interval after which cache is considered stale

    Returns:
        Tuple of (cache_hit: bool, result: Any | None)
    """
    input_data = {"func_name": func_name, "args": args, "kwargs": kwargs}

    try:
        input_hash = consistent_hash(input_data)
    except ValueError as e:
        raise ValueError(f"Failed to hash function inputs: {e}")

    cache_dir = get_cache_dir()
    output_path = cache_dir / f"{input_hash}_output.json"

    if output_path.exists():
        try:
            with output_path.open("r") as f:
                cached_data = json.load(f)

            cached_timestamp = datetime.datetime.fromisoformat(cached_data["timestamp"])

            if stale_interval is None or (datetime.datetime.now() - cached_timestamp <= stale_interval):
                with open(cached_data["pickled_output_path"], "rb") as pkl_file:
                    return True, pickle.load(pkl_file)
        except (json.JSONDecodeError, OSError, pickle.PickleError) as e:
            logger.error(f"Cache read error: {e}")

    return False, None


def save_to_cache(func_name: str, args: tuple, kwargs: dict, result: Any) -> None:
    """
    Save a result to the cache.

    Args:
        func_name: Name of the function being cached
        args: Function arguments
        kwargs: Function keyword arguments
        result: Result to cache
    """
    input_data = {"func_name": func_name, "args": args, "kwargs": kwargs}
    input_hash = consistent_hash(input_data)

    cache_dir = get_cache_dir()
    output_path = cache_dir / f"{input_hash}_output.json"
    pickled_output_path = cache_dir / f"{input_hash}_output.pkl"

    try:
        with open(pickled_output_path, "wb") as pkl_file:
            pickle.dump(result, pkl_file)

        with output_path.open("w") as f:
            json.dump(
                {
                    "pickled_output_path": str(pickled_output_path),
                    "timestamp": datetime.datetime.now().isoformat(),
                },
                f,
                indent=4,
            )
    except (OSError, pickle.PickleError) as e:
        logger.error(f"Cache write error: {e}")


def cache_with_stale_interval(
    stale_interval: datetime.timedelta | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Cache decorator with optional staleness checking.

    Args:
        stale_interval: If provided, cached results older than this will be considered stale

    Returns:
        Decorated function that implements caching with the specified staleness interval
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Try to get cached result
            cache_hit, cached_result = get_cached_result(func.__name__, args, kwargs, stale_interval)

            if cache_hit:
                return cast(R, cached_result)

            # Call the original function
            result = func(*args, **kwargs)

            # Save result to cache
            save_to_cache(func.__name__, args, kwargs, result)

            return result

        return wrapper

    return decorator
