# Delivery persistence

Core delivery records use tenant-owned SQLAlchemy tables. Revision `b4f7d2c9e105` adds dependencies, typed source/target endpoints, and milestones after `aae403476012`. Production uses forward-only Alembic upgrades and never runtime schema creation.
