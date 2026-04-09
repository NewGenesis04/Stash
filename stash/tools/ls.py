"""
ls — list the contents of a directory.
"""

from pydantic import BaseModel


class LsArgs(BaseModel):
    path: str


SCHEMA = {
    "name": "ls",
    "description": "List the files and directories at the given path.",
    "args": LsArgs.model_json_schema(),
}


def ls_tool(path: str) -> str:
    raise NotImplementedError
