"""
mv — move a file or directory from src to dst.
"""

from pydantic import BaseModel


class MvArgs(BaseModel):
    src: str
    dst: str


SCHEMA = {
    "name": "mv",
    "description": "Move a file or directory from src to dst.",
    "args": MvArgs.model_json_schema(),
}


def mv_tool(src: str, dst: str) -> str:
    raise NotImplementedError
