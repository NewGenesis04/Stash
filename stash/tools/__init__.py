from stash.tools.ls import ls_tool, SCHEMA as LS_SCHEMA
from stash.tools.mv import mv_tool, SCHEMA as MV_SCHEMA
from stash.tools.mkdir import mkdir_tool, SCHEMA as MKDIR_SCHEMA
from stash.tools.rm import rm_tool, SCHEMA as RM_SCHEMA
from stash.tools.rename import rename_tool, SCHEMA as RENAME_SCHEMA
from stash.tools.glob import glob_tool, SCHEMA as GLOB_SCHEMA

ALL_TOOLS = {
    "ls": ls_tool,
    "mv": mv_tool,
    "mkdir": mkdir_tool,
    "rm": rm_tool,
    "rename": rename_tool,
    "glob": glob_tool,
}

ALL_SCHEMAS = [LS_SCHEMA, MV_SCHEMA, MKDIR_SCHEMA, RM_SCHEMA, RENAME_SCHEMA, GLOB_SCHEMA]
