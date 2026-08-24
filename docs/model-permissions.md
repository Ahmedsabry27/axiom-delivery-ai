# Model permissions

All model APIs require authenticated tenant context and apply tenant scope; global catalogue models may be read where explicitly supported. Unknown and cross-tenant identifiers produce the same not-found response. Credential material remains server-side. Fine-grained model ownership and per-user access grants are not yet persisted.
