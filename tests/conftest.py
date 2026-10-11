"""Optional local resources used only by gateway token recounts and census audits."""

import pytest
from huggingface_hub.errors import LocalEntryNotFoundError

from klusai.privacy.datasets.data.gateway_authoring import TOKENIZER_ID, TOKENIZER_REVISION, get_tokenizer


@pytest.fixture(scope="session")
def gateway_tokenizer():
    pytest.importorskip(
        "tokenizers", reason="gateway token recount requires the optional [gateway] extra", exc_type=ModuleNotFoundError
    )
    try:
        return get_tokenizer()
    except LocalEntryNotFoundError:
        pytest.skip(f"gateway token recount requires locally cached {TOKENIZER_ID}@{TOKENIZER_REVISION}")
