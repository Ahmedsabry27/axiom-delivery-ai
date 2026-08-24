# RAID detection and human review

Candidates are durable suggestions, not RAID records. A candidate contains type, title, description, confidence, authorized evidence, affected entities, suggested owner/date/probability/impact, duplicate candidates, limitations, detector/model identifiers, trace, status, and version.

Lifecycle: `DETECTED → UNDER_REVIEW → ACCEPTED | DISMISSED | MERGED | EXPIRED`.

Creation requires at least one evidence ID. The repository verifies every ID in the authenticated tenant and runs deterministic duplicate screening before persistence. Invalid or inaccessible evidence is rejected safely. Candidate confidence is bounded to 0–1 and explicitly described as evidence-based, not certainty.

Only an authenticated user with candidate-review capability can accept, dismiss, or merge. The review UI exposes the candidate's evidence and lets the reviewer edit proposed title, description, owner, date, probability, and impact before acceptance. Acceptance applies server-side type validation, creates one persisted RAID item, carries evidence and reviewed values forward, and records the reviewer. Dismissal requires a reason. Merge preserves the existing item and attaches authorized evidence. The detector cannot approve its own candidate, and there is no automatic create/update path.

Model-backed detection may later use the established agent runtime, but invalid structured output must still fail schema/evidence validation. Current detection is deterministic and uses persisted internal evidence only.
