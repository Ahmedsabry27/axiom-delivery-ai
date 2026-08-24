# Model registry workspace

The model workspace is available at `/models`. It presents persisted tenant registry records, provider catalogue metadata, lifecycle state, aggregate usage/cost, and linked operational records. `/models/register` creates a governed `DRAFT`; it does not activate a provider or permit traffic.

Model detail routes use `/models/:id/:tab`. Unknown records are returned as non-enumerating 404 responses. Provider credentials are never returned to the browser.
