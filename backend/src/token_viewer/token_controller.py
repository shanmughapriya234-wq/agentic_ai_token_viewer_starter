"""The token viewer's controller: carries out the commands on the token model."""

from collections.abc import Callable

from token_viewer.controller import CommandError, Controller
from token_viewer.token_model import Token, TokenModel, TokenModelError
from token_viewer.view_models import (
    CaptureView,
    Message,
    TokenizerView,
    TokenView,
    ViewModel,
    ViewOption,
)


class TokenController(Controller):
    """Carries out every command as one operation on the token model."""

    def __init__(self) -> None:
        """Start with a new token model. Nothing is downloaded here."""
        self._model: TokenModel = TokenModel()

    def view_model(self) -> ViewModel:
        """Build the view-model from the model's state."""
        model: TokenModel = self._model
        tokens: list[TokenView] = [_token_view(token) for token in model.tokens()]
        tokenizer: TokenizerView | None = None
        if model.tokenizer is not None:
            tokenizer = TokenizerView(
                repository=model.repository, revision=model.revision
            )
        capture: CaptureView | None = None
        notice: str | None = None
        if model.capture_name is not None:
            capture = CaptureView(
                name=model.capture_name,
                answer=model.answer,
                reasoning=model.reasoning,
                requested_model=model.requested_model,
                reported_model=model.reported_model,
                provider=model.provider,
                status=model.status,
                finish_reason=model.finish_reason,
                prompt_tokens_reported=model.prompt_tokens_reported,
                completion_tokens_reported=model.completion_tokens_reported,
                total_tokens_reported=model.total_tokens_reported,
                prompt_tokens_local=model.prompt_tokens_local,
                elapsed_seconds=model.elapsed_seconds,
                waited_seconds=model.waited_seconds,
            )
            if model.capture_error is not None:
                notice = f"The capture has no response. {model.capture_error}"
            elif model.tokenizer is None:
                notice = (
                    "Load a model to re-tokenize the capture's answer and "
                    "reasoning and to count its prompt locally."
                )
        return ViewModel(
            tokenizer=tokenizer,
            notice=notice,
            messages=[
                Message(role=role, content=content) for role, content in model.messages
            ],
            views=[ViewOption(key=key, title=title) for key, title in model.views()],
            current_view=model.view,
            text=model.text(),
            tokens=tokens,
            selected=None if model.selected is None else tokens[model.selected],
            capture=capture,
        )

    def load_model(self, repository: str, revision: str) -> ViewModel:
        """Load the tokenizer and chat template of a model repository."""
        return self._carry_out(lambda: self._model.load(repository, revision))

    def set_messages(self, messages: list[Message]) -> ViewModel:
        """Replace the chat messages and re-tokenize them."""
        if not messages:
            raise CommandError("Give at least one message.")
        pairs: list[tuple[str, str]] = [(m.role, m.content) for m in messages]
        return self._carry_out(lambda: self._model.set_messages(pairs))

    def load_capture(self, name: str, content: str) -> ViewModel:
        """Read a capture and re-tokenize its answer and reasoning."""
        return self._carry_out(lambda: self._model.load_capture(name, content))

    def select_view(self, key: str) -> ViewModel:
        """Show another view; the model clears the selection."""
        return self._carry_out(lambda: self._model.show_view(key))

    def select_token(self, index: int) -> ViewModel:
        """Select one token of the current view."""
        return self._carry_out(lambda: self._model.select(index))

    def _carry_out(self, operation: Callable[[], None]) -> ViewModel:
        """Run one model operation and return the new view-model.

        Raises:
            CommandError: If the model refused; then nothing changed.
        """
        try:
            operation()
        except TokenModelError as refusal:
            raise CommandError(str(refusal)) from refusal
        return self.view_model()


def _token_view(token: Token) -> TokenView:
    """Turn one model token into the view-model's token."""
    return TokenView(
        index=token.index,
        id=token.id,
        piece=token.piece,
        text=token.text,
        start=token.start,
        end=token.end,
        special=token.special,
    )
