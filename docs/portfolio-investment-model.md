# Portfolio investment model

Investment values use `portfolio_investment_snapshots`, with `Numeric(19,4)` amounts, ISO currency, reporting period, source system, and source timestamp. The latest reporting snapshot wins for each entity. Legacy record metadata remains a clearly labelled compatibility fallback and is parsed with Python `Decimal`.

Missing or invalid values return `null` and render as `Not available`. When more than one currency is present, portfolio aggregation is suppressed. No currency conversion or invented financial value is performed. Delivery investment is separate from AX-EP10 AI usage budgets.
