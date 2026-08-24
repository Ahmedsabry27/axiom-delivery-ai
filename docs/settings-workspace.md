# Settings workspace

The enterprise Settings workspace uses `/settings` and category routes for profile, preferences, appearance, notifications, workspace, delivery, reporting, AI, data, features, and activity. Values come from authenticated APIs; environment secrets and safety switches are not catalogue entries.

Writes are category-scoped, transactional, validated against the typed catalogue, and require the current record version. A `409 STALE_SETTING_VERSION` response means the page must reload before retrying.
