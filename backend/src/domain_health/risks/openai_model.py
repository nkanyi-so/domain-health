"""The live model. The only module that imports the model's library.

Built only by `make eval-live` and `make record`. The deployed service never imports this module:
`openai` is in a dependency group the production image does not install, and no key is set there.
Every call goes through the spend ledger first.
"""

import time
from datetime import UTC, datetime
from typing import Protocol

import openai

from domain_health.models import SnapshotInput
from domain_health.risks import ModelOutput, Risk
from domain_health.risks.ledger import Ledger, LedgerEntry, cost_usd, most_tokens
from domain_health.risks.model import (
    CallStatus,
    ModelCall,
    input_hash,
    risks_from,
    user_message,
)
from domain_health.risks.prompt import Prompt

REASONING_EFFORT = "none"
MAX_OUTPUT_TOKENS = 2000
REQUEST_SECONDS = 60.0


class _Usage(Protocol):
    input_tokens: int
    output_tokens: int


class _Response(Protocol):
    @property
    def status(self) -> str | None: ...
    @property
    def output_text(self) -> str: ...
    @property
    def usage(self) -> _Usage | None: ...


class _Responses(Protocol):
    async def parse(
        self,
        *,
        model: str,
        instructions: str,
        input: str,
        text_format: type[ModelOutput],
        reasoning: dict[str, str],
        max_output_tokens: int,
        store: bool,
        **sampling: float,
    ) -> _Response: ...


class ResponsesClient(Protocol):
    """The one part of the library's client this module uses."""

    @property
    def responses(self) -> _Responses: ...


def client_from_environment() -> ResponsesClient:
    """The library's client. It reads `OPENAI_API_KEY` from the environment itself.

    No retries inside the library: each request is one reservation in the ledger, so a retry it
    made by itself would be a paid call the ledger never saw. A failed call is retried by
    running the command again."""
    client: ResponsesClient = openai.AsyncOpenAI(max_retries=0, timeout=REQUEST_SECONDS)  # type: ignore[assignment]
    return client


# The library's errors this module tells apart, named here so a test can raise them.
BAD_REQUEST_ERROR: type[Exception] = openai.BadRequestError
API_ERROR: type[Exception] = openai.OpenAIError


class OpenAIRiskModel:
    def __init__(
        self,
        client: ResponsesClient,
        prompt: Prompt,
        model: str,
        ledger: Ledger,
        *,
        temperature: float | None,
        purpose: str,
    ) -> None:
        self._client = client
        self._prompt = prompt
        self._model = model
        self._ledger = ledger
        self._temperature = temperature
        self._purpose = purpose

    async def call(self, snapshot: SnapshotInput) -> ModelCall:
        """One paid call, checked against the cap first, written to the ledger after."""
        message = user_message(snapshot)
        reserved = self._ledger.reserve(
            self._model, most_tokens(self._prompt.text) + most_tokens(message), MAX_OUTPUT_TOKENS
        )
        sampling = {} if self._temperature is None else {"temperature": self._temperature}
        started = time.monotonic()
        status: CallStatus = "error"
        text: str | None = None
        detail: str | None = None
        tokens_in = tokens_out = 0
        unknown_cost = False
        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=self._prompt.text,
                input=message,
                text_format=ModelOutput,
                reasoning={"effort": REASONING_EFFORT},
                max_output_tokens=MAX_OUTPUT_TOKENS,
                store=False,
                **sampling,
            )
        except BAD_REQUEST_ERROR:
            # The request itself was refused (a parameter, the schema). Nothing was generated;
            # the caller has to see this, not a silent "dropped".
            self._ledger.settle(reserved, None)
            raise
        except API_ERROR as error:
            # A timeout or a dropped connection: the model may have answered and been billed.
            status, detail, unknown_cost = "error", type(error).__name__, True
        except ValueError as error:
            # The library parses the model's text into the schema and raises if it does not fit
            # (text cut short, for one). The model did answer, so this is its answer: unusable.
            status, detail, unknown_cost = "incomplete", type(error).__name__, True
        else:
            if response.usage is not None:
                tokens_in, tokens_out = response.usage.input_tokens, response.usage.output_tokens
            else:
                unknown_cost = True
            text = response.output_text or None
            if response.status == "completed" and text:
                status = "completed"
            elif response.status == "incomplete":
                status = "incomplete"
            else:
                status, detail = "refused", f"status {response.status}, no text"
        at = datetime.now(UTC).isoformat(timespec="seconds")
        # Where what was billed is not known, the ledger takes the most it could have been.
        cost = reserved if unknown_cost else cost_usd(self._model, tokens_in, tokens_out)
        entry = LedgerEntry(
            at=at,
            purpose=self._purpose,
            model=self._model,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cost_usd=cost,
        )
        self._ledger.settle(reserved, entry)
        return ModelCall(
            prompt_version=self._prompt.version,
            prompt_sha256=self._prompt.sha256,
            model=self._model,
            reasoning_effort=REASONING_EFFORT,
            temperature=self._temperature,
            input_hash=input_hash(snapshot),
            status=status,
            output_text=text,
            detail=detail,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cost_usd=cost,
            latency_ms=int((time.monotonic() - started) * 1000),
            recorded_at=at,
        )

    async def rank(self, snapshot: SnapshotInput) -> list[Risk]:
        return risks_from(snapshot, await self.call(snapshot))
