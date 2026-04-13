"""
Shared TUI message types.

Defined here (not in app.py or widgets) so that ChatWidget can post them
and StashApp can handle them without creating a circular import.
"""

from textual.message import Message


class TaskSubmitted(Message):
    """Posted by InputArea when the user submits a task."""
    def __init__(self, task: str) -> None:
        self.task = task
        super().__init__()


class PlanApproved(Message):
    """Posted by ApproveBar when the user approves the plan."""
    pass


class PlanRejected(Message):
    """Posted by ApproveBar when the user rejects the plan."""
    pass
