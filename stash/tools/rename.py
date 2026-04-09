"""
rename — rename a file or directory within the same parent directory.
"""

from pydantic import BaseModel


class RenameArgs(BaseModel):
    path: str
    new_name: str


SCHEMA = {
    "name": "rename",
    "description": "Rename a file or directory. new_name is just the name, not a full path.",
    "args": RenameArgs.model_json_schema(),
}


def rename_tool(path: str, new_name: str) -> str:
    raise NotImplementedError
