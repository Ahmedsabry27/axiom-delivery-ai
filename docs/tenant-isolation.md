# Tenant isolation

Tenant ownership is stored on delivery tables and included in hierarchy foreign keys and common indexes. Repository constructors reject missing tenants; reads always filter by tenant; cross-tenant entity insertion and evidence association are rejected. Direct-ID isolation tests are in `backend/tests/test_delivery_persistence.py`.

This is not yet a complete authorization certification: all delivery API resources, filters, audit records, and entity-policy combinations still require an end-to-end matrix.
