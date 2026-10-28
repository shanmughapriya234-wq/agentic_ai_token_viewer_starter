"""The model: tokenizer, chat template and the state of the token viewer."""

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from huggingface_hub import hf_hub_download
from jinja2.sandbox import ImmutableSandboxedEnvironment
from tokenizers import Encoding, Tokenizer


class TokenModelError(Exception):
    """The model refused an operation and kept its state."""


@dataclass(frozen=True)
class Token:
    """One token of a view."""

    index: int
    id: int
    piece: str
    text: str
    start: int
    end: int
    special: bool


def _download(repository: str, revision: str, folder: Path, filename: str) -> Path:
    """Fetch one file of a model repository and return its local path.

    Args:
        repository: The model repository on Hugging Face, as owner/name.
        revision: The revision to take the file from.
        folder: The local folder where the file is kept.
        filename: The file's name in the repository.

    Raises:
        TokenModelError: If the download did not give a file.
    """
    path = hf_hub_download(
        repository,
        filename,
        revision=revision,
        local_dir=folder,
        token=False,  # Public files: never send a Hugging Face login.
    )
    if not isinstance(path, str):
        raise TokenModelError(f"Could not download {filename}.")
    return Path(path)


def _byte_of_character() -> dict[str, int]:
    """Return the byte that each character of a byte-level BPE piece stands for."""
    bytes_kept: list[int] = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(0xA1, 0xAC + 1))
        + list(range(0xAE, 0xFF + 1))
    )
    characters: list[int] = bytes_kept.copy()
    extra: int = 0
    for byte in range(256):
        if byte not in bytes_kept:
            bytes_kept.append(byte)
            characters.append(256 + extra)
            extra += 1
    return {chr(code): byte for byte, code in zip(bytes_kept, characters, strict=True)}


_BYTE_OF: dict[str, int] = _byte_of_character()


def _token_text(tokenizer: Tokenizer, token_id: int, piece: str) -> str:
    """Return a token's text; a piece that is only part of a character shows its bytes.

    Args:
        tokenizer: The loaded tokenizer.
        token_id: The token's ID.
        piece: The token's vocabulary entry.
    """
    text: str = tokenizer.decode([token_id], skip_special_tokens=False)
    if "\ufffd" not in text:
        return text
    raw: list[int] = [_BYTE_OF[ch] for ch in piece if ch in _BYTE_OF]
    return "<" + " ".join(f"0x{byte:02X}" for byte in raw) + ">"


def _tokens(tokenizer: Tokenizer, text: str, special_ids: set[int]) -> list[Token]:
    """Encode a text and return its tokens.

    Args:
        tokenizer: The loaded tokenizer.
        text: The text to encode. No special tokens are added to it.
        special_ids: The IDs of the special tokens.
    """
    encoding: Encoding = tokenizer.encode(text, add_special_tokens=False)
    return [
        Token(
            index=index,
            id=token_id,
            piece=piece,
            text=_token_text(tokenizer, token_id, piece),
            start=start,
            end=end,
            special=token_id in special_ids,
        )
        for index, (token_id, piece, (start, end)) in enumerate(
            zip(encoding.ids, encoding.tokens, encoding.offsets, strict=True)
        )
    ]


def _render(
    template: str, messages: list[dict[str, str]], switches: dict[str, object]
) -> str:
    """Render chat messages with a chat template, as the model would read them.

    Args:
        template: The chat template, Jinja text.
        messages: The messages, as dicts with role and content.
        switches: The template's switches, e.g. enable_thinking.
    """
    sandbox: ImmutableSandboxedEnvironment = ImmutableSandboxedEnvironment(
        trim_blocks=True, lstrip_blocks=True
    )
    rendered: str = sandbox.from_string(template).render(
        messages=messages, add_generation_prompt=True, **switches
    )
    return rendered


def _part(value: object) -> dict[str, object]:
    """Return value if it is a JSON object, otherwise an empty one."""
    if isinstance(value, dict):
        return value
    return {}


def _text(value: object) -> str | None:
    """Return value if it is a string, otherwise None."""
    return value if isinstance(value, str) else None


def _whole(value: object) -> int | None:
    """Return value if it is a whole number, otherwise None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _seconds(value: object) -> float | None:
    """Return value as a float if it is a number, otherwise None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _messages(value: object) -> list[dict[str, str]]:
    """Return the messages of a request body that have a text role and content."""
    if not isinstance(value, list):
        return []
    messages: list[dict[str, str]] = []
    for item in value:
        role: str | None = _text(_part(item).get("role"))
        content: str | None = _text(_part(item).get("content"))
        if role is not None and content is not None:
            messages.append({"role": role, "content": content})
    return messages


class TokenModel:
    """Holds the loaded tokenizer, the messages, the view and the selection."""

    def __init__(self) -> None:
        """Start with no tokenizer and no messages."""
        self.repository: str = ""
        self.revision: str = ""
        self.messages: list[tuple[str, str]] = []
        self.view: str | None = None  # The key of the view shown.
        self.selected: int | None = None  # A token's index in that view.
        self.tokenizer: Tokenizer | None = None
        self.template: str = ""
        self.special_ids: set[int] = set()
        self.chat_text: str = ""
        self.chat_tokens: list[Token] = []
        self.plain_text: str = ""
        self.plain_tokens: list[Token] = []
        self.capture_name: str | None = None  # None: no capture loaded.
        self.capture_content: str = ""  # Kept to re-tokenize after load.
        self.capture_error: str | None = None  # Why the capture has no response.
        self.answer: str | None = None
        self.reasoning: str | None = None
        self.answer_tokens: list[Token] = []
        self.reasoning_tokens: list[Token] = []
        self.requested_model: str | None = None
        self.reported_model: str | None = None
        self.provider: str | None = None
        self.status: int | None = None
        self.finish_reason: str | None = None
        self.prompt_tokens_reported: int | None = None
        self.completion_tokens_reported: int | None = None
        self.total_tokens_reported: int | None = None
        self.prompt_tokens_local: int | None = None
        self.elapsed_seconds: float | None = None
        self.waited_seconds: float | None = None

    def load(self, repository: str, revision: str) -> None:
        """Download tokenizer.json and chat_template.jinja, then load them.

        Args:
            repository: The model repository on Hugging Face, as owner/name.
            revision: The revision to take the files from.

        Raises:
            TokenModelError: If an argument is empty or the files cannot be loaded.
        """
        if not repository.strip() or not revision.strip():
            raise TokenModelError("Give both a repository and a revision.")
        folder: Path = Path(__file__).resolve().parents[2] / "downloads" / revision[:12]
        try:
            tokenizer_path: Path = _download(
                repository, revision, folder, "tokenizer.json"
            )
            template_path: Path = _download(
                repository, revision, folder, "chat_template.jinja"
            )
            tokenizer: Tokenizer = Tokenizer.from_file(str(tokenizer_path))
            template: str = template_path.read_text(encoding="utf-8")
            special_ids: set[int] = {
                token_id
                for token_id, added in tokenizer.get_added_tokens_decoder().items()
                if added.special
            }
        except Exception as error:
            raise TokenModelError(f"Could not load {repository}: {error}") from error
        self.repository = repository
        self.revision = revision
        self.tokenizer = tokenizer
        self.template = template
        self.special_ids = special_ids

        if self.view is None:
            self.view = "chat"
        if self.messages:
            self.set_messages(self.messages)
        if self.capture_name is not None:
            self.load_capture(self.capture_name, self.capture_content)

    def set_messages(self, messages: list[tuple[str, str]]) -> None:
        """Store the messages and compute the tokens of both views.

        Args:
            messages: The chat messages, as pairs of role and content.

        Raises:
            TokenModelError: If the chat template cannot be rendered.
        """
        if self.tokenizer is None:
            self.messages = messages
            return
        try:
            chat_text: str = _render(
                self.template,
                [{"role": role, "content": content} for role, content in messages],
                {"enable_thinking": False},
            )
            plain_text: str = "\n".join(content for _, content in messages)
            chat_tokens: list[Token] = _tokens(
                self.tokenizer, chat_text, self.special_ids
            )
            plain_tokens: list[Token] = _tokens(
                self.tokenizer, plain_text, self.special_ids
            )
        except Exception as error:
            raise TokenModelError(
                f"Could not tokenize the messages: {error}"
            ) from error
        self.messages = messages
        self.chat_text = chat_text
        self.chat_tokens = chat_tokens
        self.plain_text = plain_text
        self.plain_tokens = plain_tokens
        self.selected = None

    def load_capture(self, name: str, content: str) -> None:
        """Read a capture as capture-nvidia-response writes it.

        Without a tokenizer, only the texts and the metadata are read; load()
        reads the capture again and re-tokenizes it.

        Args:
            name: The capture file's name.
            content: The file's content, JSON text.

        Raises:
            TokenModelError: If the content is not a JSON object, or cannot be
                tokenized.
        """
        # 1. Turn the text into Python data.
        try:
            data: object = json.loads(content)
        except json.JSONDecodeError as error:
            raise TokenModelError(f"{name} is not valid JSON: {error}") from error
        if not isinstance(data, dict):
            raise TokenModelError(f"{name} is not a capture: expected a JSON object.")

        # 2. Open the parts. A missing part, or an error page as text, gives {}.
        request: dict[str, object] = _part(data.get("request"))
        response: dict[str, object] = _part(data.get("response"))
        request_body: dict[str, object] = _part(request.get("body"))
        response_body: dict[str, object] = _part(response.get("body"))
        choices: object = response_body.get("choices")
        first: dict[str, object] = (
            _part(choices[0]) if isinstance(choices, list) and choices else {}
        )
        message: dict[str, object] = _part(first.get("message"))
        usage: dict[str, object] = _part(response_body.get("usage"))
        problem: dict[str, object] = _part(data.get("error"))

        # 3. Read the values. The provider states the response's values; the
        #    request, the host and the times are local.
        answer: str | None = _text(message.get("content"))
        reasoning: str | None = _text(message.get("reasoning_content"))
        if reasoning is None:
            reasoning = _text(message.get("reasoning"))
        url: str = _text(request.get("url")) or ""
        provider: str | None = urlparse(url).hostname
        capture_error: str | None = None
        if problem:
            capture_error = (
                f"{_text(problem.get('type')) or 'Error'}: "
                f"{_text(problem.get('message')) or ''}"
            )
        switches: dict[str, object] = {
            key: value
            for key, value in _part(request_body.get("chat_template_kwargs")).items()
            if key not in ("messages", "add_generation_prompt")
        }
        request_messages: list[dict[str, str]] = _messages(request_body.get("messages"))

        # 4. Re-tokenize the texts and count the prompt, if a tokenizer is loaded.
        answer_tokens: list[Token] = []
        reasoning_tokens: list[Token] = []
        prompt_tokens_local: int | None = None
        if self.tokenizer is not None:
            try:
                if answer:
                    answer_tokens = _tokens(self.tokenizer, answer, self.special_ids)
                if reasoning:
                    reasoning_tokens = _tokens(
                        self.tokenizer, reasoning, self.special_ids
                    )
                if request_messages:
                    prompt: str = _render(self.template, request_messages, switches)
                    prompt_tokens_local = len(
                        _tokens(self.tokenizer, prompt, self.special_ids)
                    )
            except Exception as failure:
                raise TokenModelError(
                    f"Could not tokenize {name}: {failure}"
                ) from failure

        # 5. Store everything, only now that every step has worked.
        self.capture_name = name
        self.capture_content = content
        self.capture_error = capture_error
        self.answer = answer
        self.reasoning = reasoning
        self.answer_tokens = answer_tokens
        self.reasoning_tokens = reasoning_tokens
        self.requested_model = _text(request_body.get("model"))
        self.reported_model = _text(response_body.get("model"))
        self.provider = provider
        self.status = _whole(response.get("status_code"))
        self.finish_reason = _text(first.get("finish_reason"))
        self.prompt_tokens_reported = _whole(usage.get("prompt_tokens"))
        self.completion_tokens_reported = _whole(usage.get("completion_tokens"))
        self.total_tokens_reported = _whole(usage.get("total_tokens"))
        self.prompt_tokens_local = prompt_tokens_local
        self.elapsed_seconds = _seconds(response.get("elapsed_seconds"))
        self.waited_seconds = _seconds(data.get("waited_seconds"))
        if self.view in ("answer", "reasoning"):
            self.selected = None
            if self.view not in [key for key, _ in self.views()]:
                self.view = "chat"

    def show_view(self, key: str) -> None:
        """Switch to another view and clear the selection.

        Args:
            key: The key of the view to show, e.g. "chat" or "answer".

        Raises:
            TokenModelError: If there is no view with this key.
        """
        if key not in [known for known, _ in self.views()]:
            raise TokenModelError(f"There is no view {key!r}.")
        self.view = key
        self.selected = None

    def select(self, index: int) -> None:
        """Select one token of the current view.

        Args:
            index: The token's position in the current view, counted from 0.

        Raises:
            TokenModelError: If the view has no token with this index.
        """
        count: int = len(self.tokens())
        if not 0 <= index < count:
            raise TokenModelError(
                f"There is no token {index}: this view has {count}, numbered from 0."
            )
        self.selected = index

    def views(self) -> list[tuple[str, str]]:
        """Return the key and the title of every view."""
        views: list[tuple[str, str]] = [
            ("chat", "Chat, after the chat template"),
            ("text", "Text alone"),
        ]
        if self.answer_tokens:
            views.append(("answer", "Answer from the capture, re-tokenized"))
        if self.reasoning_tokens:
            views.append(("reasoning", "Reasoning from the capture, re-tokenized"))
        return views

    def text(self) -> str:
        """Return the text of the view shown, or "" if there is none."""
        if self.view == "chat":
            return self.chat_text
        if self.view == "text":
            return self.plain_text
        if self.view == "answer":
            return self.answer or ""
        if self.view == "reasoning":
            return self.reasoning or ""
        return ""

    def tokens(self) -> list[Token]:
        """Return the tokens of the view shown, or [] if there is none."""
        if self.view == "chat":
            return self.chat_tokens
        if self.view == "text":
            return self.plain_tokens
        if self.view == "answer":
            return self.answer_tokens
        if self.view == "reasoning":
            return self.reasoning_tokens
        return []
