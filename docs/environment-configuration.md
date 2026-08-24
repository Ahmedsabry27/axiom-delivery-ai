# Environment configuration

Copy root `.env.example` values into environment-specific secret/configuration management. Do not commit credentials. Production requires `ENVIRONMENT=production`, `RUN_SCHEMA_CREATE=false`, and `USE_MOCK_DELIVERY_DATA=false`. Frontend production builds require `VITE_USE_MOCK_DELIVERY_DATA=false` and real authentication/Cognito settings.

Developer `.env` files must not influence automated tests; test configuration explicitly resets trusted hosts and schema creation.
