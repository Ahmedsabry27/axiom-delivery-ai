# Dependency graph algorithms

The graph service is deterministic and tenant-scoped. Routes and React components do not calculate authoritative paths.

- Construction: adjacency and reverse-adjacency maps, `O(V + E)` time and memory.
- Cycle detection: iterative depth-first search with a colour map and deterministic cycle reconstruction, `O(V + E)`.
- Topological ordering: Kahn's algorithm, `O(V + E)`; cyclic graphs are rejected.
- Impact traversal: bounded breadth-first search upstream or downstream, `O(V + E)` over the authorized subgraph.
- Path search: bounded iterative depth-first enumeration. Depth and result count prevent exponential unbounded work.
- Critical path: longest edge-count path over the authorized DAG. It is classified `CALCULATED_CRITICAL_PATH` only when each path edge has required-by and forecast dates; otherwise it is `POTENTIAL_CRITICAL_PATH` with limitations. Formal float/duration is not claimed without complete timing data.
- Bottlenecks: fan-in/fan-out degree plus a delivery-impact signal. Connectivity alone is not labelled a problem.

Limits are 5,000 nodes, 20,000 edges, depth 8, and 25 returned paths. The initial visual scope is 200 nodes. Violations return safe validation errors. Cycle-creating and duplicate active relationships are rejected before commit and leave no new edge.

Measured locally on 2026-08-15 with generated DAGs: 1,000 nodes/5,000 edges—build 0.0010s, cycle 0.0024s, topological order 0.0005s, critical path 0.0020s, depth-8 impact under 0.0001s; 5,000/20,000—0.0066s, 0.0050s, 0.0025s, 0.0127s, and under 0.0001s respectively. These are algorithm microbenchmarks, not production latency claims.
