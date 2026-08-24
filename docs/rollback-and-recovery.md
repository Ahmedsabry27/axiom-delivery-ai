# Rollback and recovery

Production database changes use forward fixes: stop application promotion, preserve the database, create a new corrective Alembic revision, rehearse against a restored backup, and then promote. Do not downgrade a production database containing delivery records. Proposed-action and feedback transaction failures must roll back without external execution.
