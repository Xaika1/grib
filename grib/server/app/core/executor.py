import asyncio
import functools
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from app.config import settings

T = TypeVar("T")

_pool = ThreadPoolExecutor(max_workers=settings.query_pool_size, thread_name_prefix="grib-query")


async def run(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_pool, functools.partial(fn, *args, **kwargs))


def submit(fn: Callable[..., T], *args: Any, **kwargs: Any) -> Future:
    return _pool.submit(fn, *args, **kwargs)


def shutdown() -> None:
    _pool.shutdown(wait=False, cancel_futures=True)
