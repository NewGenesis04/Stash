"""
glob — find files matching a pattern.
"""

from pathlib import Path

from pydantic import BaseModel


class GlobArgs(BaseModel):
    pattern: str
    base_path: str = "~"


SCHEMA = {
    "type": "function",
    "function": {
        "name": "glob",
        "description": "Find files matching a glob pattern, relative to base_path.",
        "parameters": GlobArgs.model_json_schema(),
    },
    "readonly": True,
}


def glob_tool(pattern: str, base_path: str = "~") -> str:
    """
    Find files and directories matching a glob pattern.

    Searches relative to base_path. Supports standard glob syntax including
    wildcards (*), single-character wildcards (?), and recursive patterns (**).

    Args:
        pattern:   Glob pattern to match against, e.g. "*.txt", "**/*.pdf",
                   "invoices_2024_*".
        base_path: Absolute path of the directory to search from.
                   Defaults to the user's home directory.

    Returns:
        Newline-separated list of absolute paths for all matches, sorted
        alphabetically.
        Returns "(no matches)" if the pattern matched nothing.
        Returns an error string if base_path does not exist.
    """
    base = Path(base_path).expanduser()
    if not base.exists():
        return f"error: base_path does not exist: {base_path}"
    matches = sorted(base.glob(pattern))
    if not matches:
        return "(no matches)"
    return "\n".join(str(m) for m in matches)
