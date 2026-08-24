"""Compatibility exports for the centralized database session.

Database credentials must be supplied through ``DATABASE_URL`` by the deployment
secret injector.  This module intentionally contains no connection defaults.
"""

from app.database.session import SessionLocal, engine, get_db

__all__ = ["SessionLocal", "engine", "get_db"]
