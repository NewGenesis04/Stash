from stash.tools.ls import ls_tool
from stash.tools.mv import mv_tool
from stash.tools.mkdir import mkdir_tool
from stash.tools.rm import rm_tool
from stash.tools.rename import rename_tool
from stash.tools.glob import glob_tool

ALL_TOOLS = {
    "ls": ls_tool,
    "mv": mv_tool,
    "mkdir": mkdir_tool,
    "rm": rm_tool,
    "rename": rename_tool,
    "glob": glob_tool,
}
