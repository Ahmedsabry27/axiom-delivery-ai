# Axiom design system

The authoritative frontend foundation lives in `frontend/src/index.css`, shared React primitives live in `frontend/src/components/design-system`, and existing low-level UI controls remain under `frontend/src/components/ui`. The development-only showcase is `/dev/design-system`; the router excludes it from production builds.

Atomic layers are foundations → atoms → molecules → organisms → templates → pages. Route modules remain lazy loaded. The `axiom-legacy-bridge.css` file is a documented migration adapter for older tool and integration screens, not an API for new pages.

New pages must use Axiom tokens, shared components, and page templates. New page-specific UI primitives require documented justification.
