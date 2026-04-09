"""
Plan approval widget — surfaces the agent's plan for review before execution.

Shows each ReActStep (thoughts as context, actions as checkboxes). The user
approves the tool set and triggers execution, or rejects the plan entirely.
Posts PlanApproved / PlanRejected messages up the tree.
"""

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget

from stash.core.agent import ReActStep


class PlanApprovalWidget(Widget):
    class PlanApproved(Message):
        def __init__(self, approved_tools: set[str]) -> None:
            self.approved_tools = approved_tools
            super().__init__()

    class PlanRejected(Message):
        pass

    def compose(self) -> ComposeResult:
        raise NotImplementedError

    def load_plan(self, task: str, steps: list[ReActStep]) -> None:
        raise NotImplementedError
