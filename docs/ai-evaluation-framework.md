# AI evaluation framework

Evaluation datasets are tenant-scoped, named, versioned, status-controlled records containing explicit cases. A run captures dataset/version, model/version, timestamps, deterministic per-case results, scores, failure categories, schema checks, and evidence-validation output.

Security and authorization gates are ordinary deterministic checks, not model-judged assertions. Failed checks yield traceable `DETERMINISTIC_GATE_FAILED` results. Real client datasets, scheduled external runners, and model-as-judge scoring are not bundled.
