"""Step 4: reading captures, as capture-nvidia-response writes them.

The tests need no network: a tiny tokenizer is built in memory, and the
capture is a small hand-made one with the structure of a real capture.
"""

import json

import pytest
from tokenizers import Tokenizer, models

from token_viewer.token_controller import TokenController
from token_viewer.token_model import TokenModel, TokenModelError

ANSWER: str = "Tokens are pieces."
UNKNOWN: str = "[UNK]"
CAPTURE: dict[str, object] = {
    "captured_at": "2026-10-28T12:00:00+00:00",
    "waited_seconds": 1.25,
    "request": {
        "method": "POST",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "headers": {"Authorization": "<removed>"},
        "body": {
            "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
            "messages": [
                {"role": "user", "content": "Explain tokenization in one sentence."}
            ],
            "chat_template_kwargs": {"enable_thinking": False},
        },
    },
    "response": {
        "status_code": 200,
        "reason": "OK",
        "headers": {},
        "body_bytes": 300,
        "body": {
            "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": ANSWER,
                        "reasoning_content": None,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 24, "completion_tokens": 5, "total_tokens": 29},
        },
        "elapsed_seconds": 1.2,
    },
    "error": None,
}


def _model_with_tokenizer() -> TokenModel:
    """Return a model with a tiny in-memory tokenizer: one word per text."""
    model: TokenModel = TokenModel()
    model.tokenizer = Tokenizer(
        models.WordLevel(vocab={UNKNOWN: 0, ANSWER: 1}, unk_token=UNKNOWN)
    )
    model.template = "{% for m in messages %}{{ m['content'] }}{% endfor %}"
    model.view = "chat"
    return model


def test_the_metadata_is_read_without_a_tokenizer() -> None:
    model: TokenModel = TokenModel()
    model.load_capture("capture.json", json.dumps(CAPTURE))
    assert model.capture_name == "capture.json"
    assert model.answer == ANSWER
    assert model.reasoning is None
    assert model.requested_model == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert model.reported_model == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert model.provider == "integrate.api.nvidia.com"
    assert model.status == 200
    assert model.finish_reason == "stop"
    assert model.prompt_tokens_reported == 24
    assert model.completion_tokens_reported == 5
    assert model.total_tokens_reported == 29
    assert model.elapsed_seconds == 1.2
    assert model.waited_seconds == 1.25
    # Without a tokenizer, nothing is re-tokenized or counted.
    assert model.prompt_tokens_local is None
    assert "answer" not in [key for key, _ in model.views()]


def test_the_answer_is_re_tokenized_with_a_tokenizer() -> None:
    model: TokenModel = _model_with_tokenizer()
    model.load_capture("capture.json", json.dumps(CAPTURE))
    assert ("answer", "Answer from the capture, re-tokenized") in model.views()
    model.show_view("answer")
    assert model.text() == ANSWER
    assert [token.id for token in model.tokens()] == [1]
    assert model.prompt_tokens_local == 1


def test_broken_json_is_refused_and_nothing_changes() -> None:
    model: TokenModel = TokenModel()
    with pytest.raises(TokenModelError, match="not valid JSON"):
        model.load_capture("broken.json", "{not json")
    assert model.capture_name is None


def test_json_that_is_not_an_object_is_refused() -> None:
    model: TokenModel = TokenModel()
    with pytest.raises(TokenModelError, match="expected a JSON object"):
        model.load_capture("list.json", "[1, 2, 3]")


def test_a_capture_without_a_response_is_shown_with_its_error() -> None:
    no_response: dict[str, object] = {
        **CAPTURE,
        "response": None,
        "error": {"type": "ReadTimeout", "message": "timed out"},
    }
    controller: TokenController = TokenController()
    view_model = controller.load_capture("timeout.json", json.dumps(no_response))
    assert view_model.capture is not None
    assert view_model.capture.status is None
    assert view_model.capture.answer is None
    assert view_model.capture.requested_model == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert view_model.notice is not None
    assert "ReadTimeout" in view_model.notice


def test_an_error_page_as_text_gives_no_answer() -> None:
    error_page: dict[str, object] = {
        **CAPTURE,
        "response": {"status_code": 502, "body": "<html>Bad Gateway</html>"},
    }
    model: TokenModel = TokenModel()
    model.load_capture("502.json", json.dumps(error_page))
    assert model.status == 502
    assert model.answer is None
    assert model.reported_model is None
