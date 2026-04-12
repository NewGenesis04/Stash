from datetime import datetime, UTC
from typing import Literal

from pydantic import BaseModel, Field


class ReActStep(BaseModel):
    type: Literal["thought", "action", "observation", "final"]
    content: str
    tool: str | None = None
    args: dict | None = None
    result: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


# Hardcoded plan for a "clean up Downloads" task.
# Swap this out to test different scenarios.
FAKE_PLAN = [
    ReActStep(
        type="thought",
        content="I'll start by listing the contents of Downloads to understand what's there before doing anything.",
    ),
    ReActStep(
        type="action",
        tool="ls",
        args={"path": "~/Downloads"},
        content="List files in Downloads",
    ),
    ReActStep(
        type="thought",
        content="I can see 2 video files (.mp4) and a text file that's 47 days old. I'll move the videos first, then delete the stale text file.",
    ),
    ReActStep(
        type="action",
        tool="mv",
        args={"src": "~/Downloads/movie.mp4", "dst": "~/Media/Videos/movie.mp4"},
        content="Move movie.mp4 → ~/Media/Videos/",
    ),
    ReActStep(
        type="action",
        tool="mv",
        args={"src": "~/Downloads/tutorial.mp4", "dst": "~/Media/Videos/tutorial.mp4"},
        content="Move tutorial.mp4 → ~/Media/Videos/",
    ),
    ReActStep(
        type="thought",
        content="old_notes.txt is 47 days old and is not a document type listed in the keep rules. Safe to delete.",
    ),
    ReActStep(
        type="action",
        tool="rm",
        args={"path": "~/Downloads/old_notes.txt"},
        content="Delete old_notes.txt (47 days old, not a document)",
    ),
    ReActStep(
        type="final",
        content="Done. Moved 2 video files to ~/Media/Videos/. Deleted 1 stale file (old_notes.txt). Downloads is clean.",
    ),
]

# Fake observations that play back during "execution", one per action step.
FAKE_OBSERVATIONS = [
    "movie.mp4  tutorial.mp4  old_notes.txt  invoice_2025.pdf",
    "Moved: ~/Downloads/movie.mp4 → ~/Media/Videos/movie.mp4",
    "Moved: ~/Downloads/tutorial.mp4 → ~/Media/Videos/tutorial.mp4",
    "Deleted: ~/Downloads/old_notes.txt",
]
