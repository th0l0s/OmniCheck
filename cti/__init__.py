"""CTI — single-binary sentinel: one app, one scheduler, one dashboard.

Consolidation of the former 10 micro-services (Plan B of the Antirez review).
A source is one file in cti/sources/ exposing fetch(cfg, ctx) / parse(raw) /
schema(). The scheduler refreshes each on its own cadence; main.py serves the
cached result through generic routes and one JSON-driven dashboard.
"""

__version__ = "2.0.0"
