# Axiom page templates

`PageTemplate` defines canvas, gutter, and content width. `ListTemplate` composes a header, optional toolbar, and entity content. `ConfigurationTemplate` composes the common header, URL-backed navigation, and configuration content. Dashboard, detail, workbench, wizard, designer, chat, and administration variants should extend these rules only when their interaction model genuinely differs.

Every page header should expose breadcrumbs, a restrained title, useful context, actual freshness, and one clear primary action where applicable.
