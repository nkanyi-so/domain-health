"""The live model against a fake of the library's client: no key, no network, no spend."""

import json
from pathlib import Path

import pytest

from domain_health.evals.cases import load_cases
from domain_health.risks import ModelOutput
from domain_health.risks import openai_model as live
from domain_health.risks.ledger import Ledger, SpendCapError
from domain_health.risks.model import RisksUnavailableError, input_hash
from domain_health.risks.openai_model import OpenAIRiskModel
from domain_health.types import RiskType
from tests.dns_fixtures import run
from tests.eval_fixtures import MODEL, output_text, write_prompt
from tests.paths import CASES

CASE_NAME = "06-dmarc-none-established"
CASE = load_cases(CASES)[CASE_NAME]


class _Usage:
    input_tokens = 2000
    output_tokens = 600


class _Response:
    def __init__(self, text: str, status: str = "completed") -> None:
        self._text, self._status = text, status

    @property
    def status(self) -> str | None:
        return self._status

    @property
    def output_text(self) -> str:
        return self._text

    @property
    def usage(self) -> _Usage | None:
        return _Usage()


class _Responses:
    def __init__(self, outcome: _Response | Exception) -> None:
        self.outcome = outcome
        self.requests: list[dict[str, object]] = []

    async def parse(self, **request: object) -> _Response:
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        if self.outcome.status == "completed" and self.outcome.output_text:
            # As the library does: the text is parsed into the schema, and text that does not
            # fit raises here, inside the call.
            ModelOutput.model_validate_json(self.outcome.output_text)
        return self.outcome


class _Client:
    def __init__(self, outcome: _Response | Exception) -> None:
        self._responses = _Responses(outcome)

    @property
    def responses(self) -> _Responses:
        return self._responses


def model_with(
    tmp_path: Path,
    outcome: _Response | Exception,
    *,
    temperature: float | None = 0.0,
    cap: float = 1.0,
) -> tuple[OpenAIRiskModel, _Client, Ledger]:
    client = _Client(outcome)
    ledger = Ledger(tmp_path / "ledger.jsonl", cap)
    prompt = write_prompt(tmp_path / "prompts", text="Rank the risks for this domain.")
    model = OpenAIRiskModel(
        client,
        prompt,
        MODEL,
        ledger,
        temperature=temperature,
        purpose="test",
    )
    return model, client, ledger


def test_a_call_asks_for_the_schema_with_reasoning_off_and_records_what_came_back(
    tmp_path: Path,
) -> None:
    text = output_text(RiskType.DMARC_POLICY_NONE)
    model, client, ledger = model_with(tmp_path, _Response(text))

    call = run(model.call(CASE.input))

    request = client.responses.requests[0]
    assert request["model"] == MODEL
    assert request["text_format"] is ModelOutput
    assert request["reasoning"] == {"effort": "none"}
    assert request["temperature"] == 0.0
    assert request["store"] is False
    assert request["instructions"] == "Rank the risks for this domain."
    assert call.status == "completed"
    assert call.output_text == text
    assert call.input_hash == input_hash(CASE.input)
    assert (call.prompt_version, call.model) == ("risks-v1", MODEL)
    # 2,000 tokens in and 600 out on this model: $0.0005.
    assert call.cost_usd == pytest.approx(0.0005)
    assert ledger.spent() == pytest.approx(0.0005)
    assert ledger.entries()[0].purpose == "test"


def test_only_the_cases_input_reaches_the_model(tmp_path: Path) -> None:
    """Never the label, the note or the file name: the model sees what it would see in use."""
    model, client, _ = model_with(tmp_path, _Response(output_text()))

    run(model.call(CASE.input))

    request = client.responses.requests[0]
    assert json.loads(str(request["input"])) == CASE.input.model_dump(mode="json")
    sent = json.dumps({key: str(value) for key, value in request.items()})
    assert CASE.note not in sent
    assert CASE.note[:40] not in sent
    assert CASE_NAME not in sent
    assert '"expected"' not in sent
    assert '"acceptable"' not in sent
    assert '"wrong"' not in sent
    assert '"label"' not in sent


def test_with_no_temperature_set_the_parameter_is_not_sent(tmp_path: Path) -> None:
    model, client, _ = model_with(tmp_path, _Response(output_text()), temperature=None)

    call = run(model.call(CASE.input))

    assert "temperature" not in client.responses.requests[0]
    assert call.temperature is None


def test_rank_gives_validated_risks_with_ids_built_in_code(tmp_path: Path) -> None:
    model, _, _ = model_with(tmp_path, _Response(output_text(RiskType.DKIM_KEY_1024)))

    risks = run(model.rank(CASE.input))

    assert [risk.id for risk in risks] == [f"dkim_key_1024:{CASE.input.domain}"]


def test_output_the_schema_allows_but_a_rule_forbids_is_paid_for_and_dropped(
    tmp_path: Path,
) -> None:
    twice = output_text(RiskType.VOLUME_SPIKE, RiskType.VOLUME_SPIKE)
    model, _, ledger = model_with(tmp_path, _Response(twice))

    with pytest.raises(RisksUnavailableError, match="invalid output dropped"):
        run(model.rank(CASE.input))

    assert ledger.spent() == pytest.approx(0.0005)


def test_text_the_library_cannot_parse_is_recorded_and_charged_at_the_worst_case(
    tmp_path: Path,
) -> None:
    """The library raises when the model's text does not fit the schema (cut short, say). That
    is an answer, not a crash: it is recorded, never asked again, and the ledger takes the most
    the call could have cost, because what was billed is not known."""
    model, _, ledger = model_with(tmp_path, _Response('{"risks": [{"type": "volume_sp'))

    call = run(model.call(CASE.input))

    assert call.status == "incomplete"
    assert call.output_text is None
    assert call.cost_usd > 0.001
    assert ledger.spent() == pytest.approx(call.cost_usd)
    assert len(ledger.entries()) == 1
    # Nothing is left reserved: the next call is judged against what was written down.
    worst = ledger.reserve(MODEL, 1, 1)
    assert ledger.spent() + worst < 1.0


@pytest.mark.parametrize(
    ("response", "status"),
    [(_Response("", "incomplete"), "incomplete"), (_Response("", "completed"), "refused")],
)
def test_an_answer_with_no_usable_text_is_recorded_as_what_it_was(
    tmp_path: Path, response: _Response, status: str
) -> None:
    model, _, _ = model_with(tmp_path, response)

    call = run(model.call(CASE.input))

    assert call.status == status
    assert call.output_text is None


def test_a_failed_call_is_recorded_as_an_error_at_the_most_it_could_have_cost(
    tmp_path: Path,
) -> None:
    # A timeout can come after the model has answered and been billed.
    model, _, ledger = model_with(tmp_path, live.API_ERROR("the connection dropped"))

    call = run(model.call(CASE.input))

    assert call.status == "error"
    assert call.output_text is None
    assert call.cost_usd > 0.001
    assert ledger.spent() == pytest.approx(call.cost_usd)
    assert len(ledger.entries()) == 1


def test_the_library_makes_no_retry_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-key")

    client = live.client_from_environment()

    assert client.max_retries == 0  # type: ignore[attr-defined]


def test_a_refused_request_is_raised_not_recorded(tmp_path: Path) -> None:
    # The library's own error for a request it will not take, made without its constructor
    # (which wants a real HTTP response).
    refused = live.BAD_REQUEST_ERROR.__new__(live.BAD_REQUEST_ERROR)
    model, _, ledger = model_with(tmp_path, refused)

    with pytest.raises(live.BAD_REQUEST_ERROR):
        run(model.call(CASE.input))

    assert ledger.entries() == []


def test_past_the_cap_no_request_is_made(tmp_path: Path) -> None:
    model, client, ledger = model_with(tmp_path, _Response(output_text()), cap=0.0001)

    with pytest.raises(SpendCapError):
        run(model.call(CASE.input))

    assert client.responses.requests == []
    assert ledger.entries() == []


def test_a_call_cut_off_while_waiting_is_written_down_at_its_worst_case(tmp_path: Path) -> None:
    """When another call of the run fails, or the run is interrupted, the calls still waiting
    are cancelled. Their requests went out and may be billed, so each is in the ledger."""
    import asyncio

    class _Hanging(_Responses):
        async def parse(self, **request: object) -> _Response:
            self.requests.append(request)
            await asyncio.sleep(60)
            raise AssertionError("never reached")

    model, client, ledger = model_with(tmp_path, _Response(output_text()))
    client._responses = _Hanging(_Response(output_text()))

    async def cut_off() -> None:
        tasks = [asyncio.create_task(model.call(CASE.input)) for _ in range(5)]
        await asyncio.sleep(0.01)
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)

    run(cut_off())

    assert len(client.responses.requests) == 5
    assert len(ledger.entries()) == 5
    assert all(entry.cost_usd > 0.001 for entry in ledger.entries())
    # Nothing stays reserved once they are written down.
    assert ledger.spent() == pytest.approx(sum(entry.cost_usd for entry in ledger.entries()))


def test_the_worst_case_counts_the_schema_and_the_framing_too(tmp_path: Path) -> None:
    import json

    from domain_health.risks.ledger import cost_usd, most_tokens
    from domain_health.risks.model import user_message

    model, _, _ = model_with(tmp_path, live.API_ERROR("the connection dropped"))

    call = run(model.call(CASE.input))

    schema = most_tokens(json.dumps(ModelOutput.model_json_schema()))
    assert live.SCHEMA_TOKENS == schema > 1000
    most_input = (
        most_tokens("Rank the risks for this domain.")
        + most_tokens(user_message(CASE.input))
        + schema
        + live.FRAMING_TOKENS
    )
    assert call.cost_usd == pytest.approx(cost_usd(MODEL, most_input, live.MAX_OUTPUT_TOKENS))
