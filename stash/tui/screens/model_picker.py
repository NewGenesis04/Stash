"""
Model picker screen — shown on first run or when the configured model is missing.

Fetches available models from Ollama, lets the user select one, then saves
the selection to config.toml before dismissing. Dismissed with the selected
model name, or raises SystemExit if the user quits without picking.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen


class ModelPickerScreen(ModalScreen[str]):
    """
    Receives the list of available models and the config path.
    Dismisses with the selected model name.
    """

    def __init__(self, available_models: list[str]) -> None:
        super().__init__()
        self.available_models = available_models

    def compose(self) -> ComposeResult:
        raise NotImplementedError
