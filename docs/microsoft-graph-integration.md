# Microsoft Graph integration

Outlook Calendar and Teams Meetings share a Microsoft provider authorization but keep independent configuration, status, scope, mappings, cursors, runs, quality, subscriptions, and audit. Server-side authorization state is random, hashed at rest, ten-minute limited, one-time, and tenant/user bound. Only opaque secret references are stored.

The implementation is simulator-backed. Live Entra code exchange with PKCE, token rotation, Graph delta handling, notification validation, tenant confirmation, and sandbox certification require a dedicated Microsoft test tenant and are not enabled.
