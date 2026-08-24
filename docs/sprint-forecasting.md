# Sprint forecasting

The initial forecast blends projected observed throughput (60%) with historical median completed points (40%). It then applies transparent penalties for blocked points and added scope, constrains output to plausible sprint bounds, and returns completed points, carryover, a ± uncertainty range, goal confidence, method, generated time, and limitations.

At least completed points, elapsed/total days, and original commitment are required. Fewer than three historical sprints adds a limitation and increases reliance on observed throughput. Goal confidence reflects forecast coverage and goal-critical blocker exposure; it is not model certainty and does not produce a forecast when inputs are insufficient.
