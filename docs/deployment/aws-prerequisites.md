# AWS deployment prerequisites

- AWS account `594677690649`, target region `eu-west-2`, staging environment.
- Terraform CLI and AWS provider versions pinned by the future infrastructure root.
- A confirmed GitHub repository remote.
- GitHub OIDC provider and repository/environment-scoped deploy roles.
- Separate remote Terraform state for staging and production with encryption and locking.
- Cognito identifiers, database secret reference, provider secret references, CORS origins, trusted hosts, and public API URL supplied through AWS/GitHub configuration—not committed files.
- Optional domains and Route 53 hosted zones. Generated CloudFront and ALB URLs are sufficient for initial staging.

Never provide AWS keys or application secrets in chat or commit them to Git. If the AWS session expires, authenticate using the configured profile and the organization-approved login method.
