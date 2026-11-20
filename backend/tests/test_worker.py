"""The worker's core: checks, rules, model, snapshot, for one seeded client on one day."""

import json
import logging
from datetime import UTC, date, datetime

import pytest

from domain_health.clock import FixedClock
from domain_health.risks import MAX_RISKS
from domain_health.risks.model import FixtureRiskModel, input_hash
from domain_health.seeded import load_clients, snapshot_input
from domain_health.store import SHARED
from domain_health.store.memory import MemoryStore
from domain_health.types import RiskType
from domain_health.worker import ModelFacts, main, run_client
from tests.dns_fixtures import run
from tests.paths import REPO

CLIENT = load_clients()[0]
DAY = date(2026, 3, 1)
CLOCK = FixedClock(datetime(2026, 3, 1, 6, 30, tzinfo=UTC))
FACTS = ModelFacts(prompt_version="risks-v0", model="a-model")
TYPES = [kind.value for kind in RiskType]


def output(count: int) -> str:
    return json.dumps(
        {
            "risks": [
                {"type": kind, "title": "A title", "why": "A reason.", "evidence": ["fixes"]}
                for kind in TYPES[:count]
            ]
        }
    )


def model(text: str | None) -> FixtureRiskModel:
    return FixtureRiskModel({} if text is None else {CLIENT.domain: text})


def test_a_run_saves_the_day_with_checks_fixes_and_ranked_risks() -> None:
    store = MemoryStore()
    fake = model(output(7))

    snapshot = run(run_client(CLIENT, DAY, model=fake, facts=FACTS, store=store, clock=CLOCK))

    expected_input = run(snapshot_input(CLIENT, DAY))
    assert fake.seen == [expected_input]
    assert snapshot.checks.model_input() == expected_input.checks
    assert snapshot.fixes == expected_input.fixes
    assert snapshot.sources == expected_input.sources
    assert snapshot.input_hash == input_hash(expected_input)
    assert [risk.id for risk in snapshot.ranked] == [
        f"{kind}:{CLIENT.domain}" for kind in TYPES[:7]
    ]
    assert snapshot.visible == snapshot.ranked[:5]
    assert snapshot.risks_status == "ranked"
    assert (snapshot.prompt_version, snapshot.model, snapshot.model_source) == (
        "risks-v0",
        "a-model",
        "recorded",
    )
    assert snapshot.started_at == snapshot.finished_at == CLOCK.now()
    stored = run(store.read_day(SHARED, CLIENT.id, DAY, CLOCK.now()))
    assert stored is not None
    assert stored.snapshot == snapshot


def test_run_twice_for_one_day_leaves_one_document() -> None:
    store = MemoryStore()
    for _ in range(2):
        run(run_client(CLIENT, DAY, model=model(output(3)), facts=FACTS, store=store, clock=CLOCK))

    assert store.documents == 1
    assert list(store.snapshots) == [(CLIENT.id, DAY)]


def test_a_dry_run_returns_the_document_and_writes_nothing() -> None:
    store = MemoryStore()

    snapshot = run(
        run_client(
            CLIENT, DAY, model=model(output(6)), facts=FACTS, store=store, clock=CLOCK, dry_run=True
        )
    )

    assert len(snapshot.ranked) == 6
    assert len(snapshot.visible) == 5
    assert store.documents == 0


def test_a_dry_run_shows_the_marks_that_are_there() -> None:
    store = MemoryStore()
    first = run(
        run_client(CLIENT, DAY, model=model(output(6)), facts=FACTS, store=store, clock=CLOCK)
    )
    run(store.mark(SHARED, CLIENT.id, DAY, first.ranked[0].id, CLOCK.now()))

    preview = run(
        run_client(
            CLIENT, DAY, model=model(output(6)), facts=FACTS, store=store, clock=CLOCK, dry_run=True
        )
    )

    assert preview.suppressed == [first.ranked[0]]
    assert preview.visible == first.ranked[1:6]


@pytest.mark.parametrize(
    "text",
    [
        None,
        "not json",
        json.dumps({"risks": [{"type": "made_up", "title": "t", "why": "w", "evidence": []}]}),
        output(MAX_RISKS + 1),
        json.dumps(
            {
                "risks": [
                    {
                        "type": TYPES[0],
                        "title": "A title",
                        "why": "The rate is 99.123 percent.",
                        "evidence": ["fixes"],
                    }
                ]
            }
        ),
    ],
    ids=["no answer", "not json", "unknown type", "nine risks", "invented number"],
)
def test_a_model_failure_or_invalid_output_saves_fixes_and_risks_unavailable(
    text: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    store = MemoryStore()

    with caplog.at_level(logging.WARNING):
        snapshot = run(
            run_client(CLIENT, DAY, model=model(text), facts=FACTS, store=store, clock=CLOCK)
        )

    assert snapshot.risks_status == "unavailable"
    assert snapshot.risks_unavailable_reason
    assert (snapshot.ranked, snapshot.visible, snapshot.suppressed) == ([], [], [])
    assert snapshot.fixes == run(snapshot_input(CLIENT, DAY)).fixes
    assert store.documents == 1
    assert f"risks unavailable for {CLIENT.id}" in caplog.text


def test_the_command_is_a_dry_run_that_prints_the_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = str(REPO / "prompts" / "risks-v3.md")

    code = main([CLIENT.id, "--date", "2026-03-01", "--prompt", prompt, "--model", "a-model"])

    printed = capsys.readouterr().out
    assert code == 0
    assert printed.startswith("dry run: nothing was written.")
    document = json.loads(printed.split("\n", 1)[1])
    assert document["client_id"] == CLIENT.id
    assert document["day"] == "2026-03-01"
    assert document["risks_status"] == "unavailable"
    assert document["prompt_version"] == "risks-v3"


def test_the_command_refuses_a_client_that_is_not_seeded(
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = str(REPO / "prompts" / "risks-v3.md")

    assert main(["nobody", "--prompt", prompt, "--model", "a-model"]) == 2
    assert "no seeded client" in capsys.readouterr().err
