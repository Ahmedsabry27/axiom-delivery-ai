# Workflow designer

The designer stores an ordered graph in `definition.nodes` and `definition.edges`. Supported node types are `start`, `end`, `agent`, `tool`, `condition`, `approval`, `human_input`, and `notification`. Keyboard-accessible add, move, edit, and remove controls are provided without requiring drag and drop.

Backend validation checks collection shape, unique node IDs, required start/end nodes, supported types, and edge references. Arbitrary scripts and webhook nodes are not exposed.
