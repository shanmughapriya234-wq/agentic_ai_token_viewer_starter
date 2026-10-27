"""The terminal view of the token viewer: prints the tokens of the views."""

import argparse
import io
import json
import sys
from pathlib import Path

from token_viewer.controller import CommandError
from token_viewer.view_models import Message, ViewModel
from token_viewer.wiring import build_controller

DEFAULT_REPOSITORY: str = "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4"
DEFAULT_REVISION: str = "bee7596271d1495f6992ae224aefde4410e816b8"
DEFAULT_MESSAGES: list[Message] = [
    Message(role="user", content="Explain tokenization in one sentence.")
]


def _show(view_model: ViewModel) -> None:
    """Print the text and the tokens of the current view."""
    titles: dict[str, str] = {option.key: option.title for option in view_model.views}
    key: str = view_model.current_view or ""
    print(f"\n=== {titles.get(key, key)} ===")
    print(f"Text: {view_model.text!r}\n")
    print("  idx       ID  start-end  vocabulary entry  decoded text")
    for token in view_model.tokens:
        mark: str = "  special token" if token.special else ""
        span: str = f"{token.start}-{token.end}"
        print(
            f"  {token.index:>3}  {token.id:>7}  {span:>9}  "
            f"{token.piece!r:<16}  {token.text!r}{mark}"
        )
    print(f"\nCount: {len(view_model.tokens)} tokens")


def _read_messages(path: str | None) -> list[Message]:
    """Read the messages from a JSON file, or use the course request."""
    if path is None:
        return DEFAULT_MESSAGES
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Message.model_validate(item) for item in data]


def main() -> None:
    """Load the model, set the messages and print every view."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Show the tokens of a chat request.")
    parser.add_argument("--messages", help="JSON file with the chat messages")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    args = parser.parse_args()
    try:
        messages: list[Message] = _read_messages(args.messages)
        controller = build_controller()
        view_model: ViewModel = controller.load_model(args.repository, args.revision)
        controller.set_messages(messages)
        for option in view_model.views:
            _show(controller.select_view(option.key))
    except (CommandError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
