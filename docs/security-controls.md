# Security controls

Production rejects mock delivery mode and schema auto-create. Delivery access is authenticated and tenant scoped. Secret scanning prints file/classification only, not values. Current npm production audit is clean. Python audit retains one ECDSA transitive advisory; Cognito validation is fixed to RS256, but dependency replacement remains recommended.
