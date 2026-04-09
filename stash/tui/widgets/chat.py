"""
Chat widget — task input and live ReAct stream.

Accepts natural language tasks, streams ReAct steps as they execute,
and displays the final answer. Posts TaskSubmitted messages up the tree.
"""

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget


class ChatWidget(Widget):
    class TaskSubmitted(Message):
        def __init__(self, task: str) -> None:
            self.task = task
            super().__init__()

    def compose(self) -> ComposeResult:
        raise NotImplementedError
