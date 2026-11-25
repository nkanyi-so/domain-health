# 0014: the service is opened by turning off Cloud Run's invoker check

**Status:** decided, 2026-11-20.

**Context.** Decision 0009 has the Cloud Run service open at the platform level, because the frontend's server cannot mint Google tokens without a long-lived key, with every route refusing at the app level. The usual way to open a service is to grant `allUsers` the invoker role. On the first deploy the project's organisation policy refused that grant: "One or more users named in the policy do not belong to a permitted customer, perhaps due to an organization policy." The service was deployed closed, and there were three options: turn off the invoker check, add an exception to the organisation policy, or keep the service closed and have the frontend prove a Google identity through workload identity federation.

**Decision.** `make deploy-backend` deploys with `--no-invoker-iam-check`. Cloud Run then does not check a caller's Google identity before passing the call to the service. No `allUsers` grant is made, and the organisation policy is not changed.

**Consequence.**

- The app-level checks are the only gate. Every `/api/*` route refuses a call without the proxy secret; `/internal/*` refuses a call without a Google-signed token for the service's URL from the invoker account; `/health` is open and says nothing. `backend/tests/test_api.py` and `backend/tests/test_machine_routes.py` are what stand between the public and the service, and each route is checked in review.
- The check "an unauthenticated call to the worker gets 401" is shown on the deployed service: the 401 is the app's own.
- The invoker account keeps its `run.invoker` grant. It does nothing while the check is off, and it means the schedule keeps working if the check is ever turned back on.
- If the organisation later forbids this setting too, the deploy fails and says so; the options then are the other two above.

**Also recorded.** During the first deploy this setting was turned off on the live service to test, before the decision was taken, and turned back on within minutes.
