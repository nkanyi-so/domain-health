"""Shows that `make check` really runs tests inside the Firestore emulator.

Phase 3 replaces this with the store's own emulator tests. It talks to localhost only, with the
standard library, because the Firestore client is not a dependency until the store exists.
"""

import os
import urllib.request

import pytest

pytestmark = pytest.mark.emulator


def test_the_firestore_emulator_answers() -> None:
    host = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
    assert host.startswith(("127.0.0.1:", "localhost:")), "run through `make check`"

    with urllib.request.urlopen(f"http://{host}/", timeout=5) as response:
        assert response.status == 200
