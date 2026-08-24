# Model pricing and cost

Prices use the existing effective-dated `ModelPrice` records. Runtime budget enforcement uses decimal arithmetic and reserves estimated cost before execution, then settles or releases it after execution. The UI reports persisted usage cost and does not estimate missing prices in the browser.
