# Outlook Calendar connector

The connector is calendar-only: no mail permissions or mailbox content are requested. The deterministic dataset contains two calendars, nine events, and three recurring series. Events map to Meetings with durable lineage; schedule, organizer, attendees, cancellation, recurrence, and timezone remain Outlook-authoritative.

The simulator persists a renewable event-subscription record. Live Graph delta queries, recurrence expansion, cancellation reconciliation, subscription validation/renewal, canonical Meeting writes, and approved create/update/cancel execution remain pending sandbox work.
