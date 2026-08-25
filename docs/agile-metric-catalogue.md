# Agile metric catalogue

The executable catalogue is `backend/app/delivery/metrics.py`. Each definition has a stable key, display name, version, formula, unit, direction, thresholds, minimum sample, applicable entity types, and missing-data behavior.

Headline formulas include:

- Sprint goal achievement = achieved sprint goals / eligible sprint goals × 100.
- Commitment achievement = completed originally committed work / originally committed work × 100.
- Carryover rate = incomplete originally committed work / originally committed work × 100.
- Forecast accuracy = 100 − absolute(forecast − actual) / forecast × 100.
- Evidence coverage = evidence-backed eligible records / eligible records × 100.

A missing numerator, missing denominator, or non-positive denominator produces `UNKNOWN`; it never becomes zero.
