import logging

from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def setup_database_metrics(engine: Engine) -> None:
    """
    Initialize database observability.

    Database metrics are collected at the repository layer
    (ConversationRepository and MessageRepository).

    SQLAlchemy event listeners have been removed to avoid
    double-counting queries and to provide more meaningful
    application-level metrics.
    """

    logger.info("Database metrics initialized.")
