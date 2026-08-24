# Migration and seeding

Run migrations from `backend` with `alembic upgrade head`. AX-H01 adds revision `aae403476012`; a clean SQLite database was successfully upgraded through all revisions to this head.

Production startup must not create schemas automatically and must not seed demo records. Demo/test data belongs only in explicit local or test workflows. A downgrade rehearsal and production-engine migration test remain outstanding.
