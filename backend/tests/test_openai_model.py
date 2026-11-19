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


def test_invalid_output_is_paid_for_and_dropped(tmp_path: Path) -> None:
    model, _, ledger = model_with(tmp_path, _Response('{"risks": "many"}'))

    with pytest.raises(RisksUnavailableError, match="invalid output dropped"):
        run(model.rank(CASE.input))

    assert ledger.spent() == pytest.approx(0.0005)


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


def test_a_failed_call_is_recorded_as_an_error_at_no_cost(tmp_path: Path) -> None:
    model, _, ledger = model_with(tmp_path, live.API_ERROR("the connection dropped"))

    call = run(model.call(CASE.input))

    assert call.status == "error"
    assert call.output_text is None
    assert call.cost_usd == 0
    assert ledger.spent() == 0
    assert len(ledger.entries()) == 1


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
