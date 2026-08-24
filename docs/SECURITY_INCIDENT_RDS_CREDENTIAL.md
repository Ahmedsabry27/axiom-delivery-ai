# RDS credential containment action

Status: code containment completed; external response remains open.

A database credential was previously embedded in a tracked backend module. The
current source now requires `DATABASE_URL` from the deployment environment and
sanitizes credential-bearing URLs and database exceptions at public/logging
boundaries. The repository history was intentionally not rewritten.

An authorized operator must complete all of the following outside this change:

1. Revoke and rotate the affected RDS credential immediately.
2. Review database authentication, query, and network access logs for misuse.
3. Review CI, application, observability, and support logs for copied values.
4. Review forks, clones, build artifacts, deployment packages, and caches.
5. Perform an approved repository-history cleanup if incident policy requires it.
6. Confirm applications use the replacement through the approved secret injector.

Do not restore a connection-string default in source code, tests, images, or CI.
