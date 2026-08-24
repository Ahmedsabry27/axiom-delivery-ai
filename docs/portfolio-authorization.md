# Portfolio authorization

The Portfolio endpoint requires the existing application authentication dependency. Tenant identity and user identity come from trusted claims; client-supplied tenant identifiers are ignored. Every query includes the tenant predicate.

When an identity carries explicit permissions, `portfolio.read` is required. Financial values additionally require `portfolio.financials.read`; platform administrators retain access. Legacy authenticated identities without a permission claim remain compatible. Restricted responses preserve the non-financial shape and redact financial values server-side. Cross-tenant service behavior is covered by focused tests.

Entity-level grants are not yet persisted; authorization below the tenant boundary remains a production-readiness gap.
