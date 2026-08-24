# Axiom design tokens

Use the `--axiom-*` semantic properties rather than hardcoded colours or page-specific values. Families cover canvas/surfaces, text, borders, brand, semantic status, spacing, geometry, control dimensions, shell dimensions, elevation, and motion.

Rectangular structural surfaces use no or small radius. Medium radius is reserved for overlays; full radius is reserved for statuses and compact tags. Borders are preferred over shadows. Breakpoints follow the Tailwind mobile-first system already configured by the project; components must not invent local breakpoint values.
