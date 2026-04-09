"""
rm — delete a file. Does not delete directories.
"""

from pydantic import BaseModel


class RmArgs(BaseModel):
    path: str


SCHEMA = {
    "name": "rm",
    "description": "Delete a file at the given path. Will not delete directories.",
    "args": RmArgs.model_json_schema(),
}


def rm_tool(path: str) -> str:
    raise NotImplementedError
