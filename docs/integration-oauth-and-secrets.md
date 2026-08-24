# Integration OAuth and secrets

Provider connect and callback processing is backend-only. State is generated with a cryptographic RNG, stored only as SHA-256, expires after ten minutes, is bound to provider/tenant/initiating user, and can be consumed once. Local HTTP redirects are accepted only for localhost; deployed callbacks require HTTPS.

Database/API/log-safe fields include provider, account label, provider tenant/site ID, scopes, expiry, status, verification times, and an opaque secret reference. Access/refresh tokens, client secrets, certificates, and PKCE verifier values are never returned. `env://` and AWS Secrets Manager are production boundaries; `simulator://` is a value-free deterministic test provider. Disconnect removes/revokes the reference without deleting imported records.
