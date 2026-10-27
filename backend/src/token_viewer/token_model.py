"""The model: tokenizer, chat template and the state of the token viewer."""

from dataclasses import dataclass
from pathlib import Path

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
            sandbox: ImmutableSandboxedEnvironment = ImmutableSandboxedEnvironment(
                trim_blocks=True, lstrip_blocks=True
            )
            chat_text: str = sandbox.from_string(self.template).render(
                messages=[
                    {"role": role, "content": content} for role, content in messages
                ],
                add_generation_prompt=True,
                enable_thinking=False,
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

    def show_view(self, key: str) -> None:
        """Switch to the view "chat" or "text" and clear the selection.

        Args:
            key: The key of the view to show.

        Raises:
            TokenModelError: If there is no view with this key.
        """
        if key not in ("chat", "text"):
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
        return [("chat", "Chat, after the chat template"), ("text", "Text alone")]

    def text(self) -> str:
        """Return the text of the view shown, or "" if there is none."""
        if self.view == "chat":
            return self.chat_text
        if self.view == "text":
            return self.plain_text
        return ""

    def tokens(self) -> list[Token]:
        """Return the tokens of the view shown, or [] if there is none."""
        if self.view == "chat":
            return self.chat_tokens
        if self.view == "text":
            return self.plain_tokens
        return []
