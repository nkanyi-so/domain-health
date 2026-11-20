"""The deployed service: the app built from its real parts. `uvicorn domain_health.serve:app`.

The model is the recorded one and nothing else: the answers `make record` saved, replayed. No
model library is imported here and no model key is read.

With `DOMAIN_HEALTH_DEV=1` and the Firestore emulator's address set, it builds a local version
for `make dev`: the emulator's database, a queue that only remembers, no alerts, and no machine
caller accepted at all.
"""

import os

from fastapi import FastAPI

from domain_health.alerts import Alerter, NullAlerter
from domain_health.app import Deps, create_app
from domain_health.clock import SystemClock
from domain_health.machine_auth import GoogleKeySet, StaticKeySet
from domain_health.resolver import Resolver
from domain_health.seeded import load_clients
from domain_health.seeded.recordings import recorded_model
from domain_health.settings import Settings
from domain_health.store.firestore import connect
from domain_health.tasks import FakeQueue
from domain_health.worker import ModelFacts

DEV_PROXY_SECRET = "dev-only-proxy-secret"  # noqa: S105
DEV_PROJECT = "demo-domain-health"


def _live_resolver() -> Resolver:
    # Imported here, and called only by the live-check route after its limits: nothing else in
    # the service can reach real DNS. TCP, because UDP out of the host is not a given.
    from domain_health.resolver.live import LiveResolver

    return LiveResolver(tcp=True)


def production() -> Deps:
    from domain_health.cloud_tasks import CloudTasksQueue
    from domain_health.slack import SlackWebhookAlerter

    settings = Settings()
    model, prompt, model_name = recorded_model()
    webhook = settings.slack_webhook_url.get_secret_value() if settings.slack_webhook_url else ""
    alerter: Alerter = SlackWebhookAlerter(webhook) if webhook else NullAlerter()
    return Deps(
        store=connect(settings.gcp_project_id),
        clock=SystemClock(),
        clients=tuple(load_clients()),
        model=model,
        facts=ModelFacts(prompt_version=prompt.version, model=model_name),
        queue=CloudTasksQueue(
            project=settings.gcp_project_id,
            region=settings.gcp_region,
            queue=settings.tasks_queue,
            service_url=settings.service_url,
            invoker_email=settings.invoker_email,
        ),
        alerter=alerter,
        keys=GoogleKeySet(),
        live_resolver=_live_resolver,
        proxy_secret=settings.proxy_secret.get_secret_value(),
        service_url=settings.service_url.rstrip("/"),
        invoker_email=settings.invoker_email,
    )


def development() -> Deps:
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
    if not host.startswith(("127.0.0.1:", "localhost:")):
        raise RuntimeError("DOMAIN_HEALTH_DEV=1 runs against the Firestore emulator only")
    model, prompt, model_name = recorded_model()
    return Deps(
        store=connect(DEV_PROJECT),
        clock=SystemClock(),
        clients=tuple(load_clients()),
        model=model,
        facts=ModelFacts(prompt_version=prompt.version, model=model_name),
        queue=FakeQueue(),
        alerter=NullAlerter(),
        # No key at all: every machine call is refused locally.
        keys=StaticKeySet({}),
        live_resolver=_live_resolver,
        proxy_secret=DEV_PROXY_SECRET,
        service_url="http://127.0.0.1:8000",
        invoker_email="nobody@localhost",
    )


def build() -> FastAPI:
    dev = os.environ.get("DOMAIN_HEALTH_DEV") == "1"
    return create_app(development() if dev else production())


app = build()
