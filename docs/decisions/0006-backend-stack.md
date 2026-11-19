# 0006: backend on Python 3.14, FastAPI, uv, dnspython

**Status:** accepted, 2026-11-19 (intake)

**Context.** The backend is a small pipeline with an HTTP surface, DNS lookups, a document store and a container to ship.

**Decision.** Python 3.14 with FastAPI and pydantic, as in the other two demos, so the three read as one hand. `uv` for dependencies and the lockfile. Ruff for format and lint, mypy in strict mode, pytest. `dnspython` for DNS: its async resolver gives per-query timeouts and typed answers, and its exceptions separate "no such name" from "no answer" from a timeout, which the checks need. Google's own client libraries for Firestore and Cloud Tasks, and `google-auth` to verify OIDC tokens. A Dockerfile, because Cloud Run runs containers.

**Consequence.** One language for the pipeline, the evals and the scripts. The Google libraries are heavy, so they stay inside their implementation modules (rule 1 in `CLAUDE.md`) and the unit tests never import them. Not verified at the intake: that outbound DNS over UDP works from Cloud Run. Phase 4's gate checks a live lookup on the deployed service; the fallback is DNS over TCP, which `dnspython` does with one argument. Each package's current API is checked in the phase that first uses it.
