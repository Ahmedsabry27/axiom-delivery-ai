from contextlib import contextmanager
from time import perf_counter

from app.logging.logger import logger


@contextmanager
def trace(operation: str):
    start = perf_counter()

    logger.info("Starting %s", operation)

    try:
        yield
    finally:
        duration = perf_counter() - start
        logger.info("Completed %s in %.3fs", operation, duration)
