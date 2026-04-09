"""
Rule editor screen — create and edit folder rules.

Pushed onto the screen stack from the sidebar. Dismissed with the updated
FolderRule on save, or None on cancel.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen

from stash.persistence.tinydb import FolderRule


class RuleEditorScreen(ModalScreen[FolderRule | None]):
    def __init__(self, rule: FolderRule | None = None) -> None:
        super().__init__()
        self.rule = rule  # None means creating a new rule

    def compose(self) -> ComposeResult:
        raise NotImplementedError
