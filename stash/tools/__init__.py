from stash.tools.ls import ls_tool, SCHEMA as LS_SCHEMA, LsArgs
from stash.tools.mv import mv_tool, SCHEMA as MV_SCHEMA, MvArgs
from stash.tools.mkdir import mkdir_tool, SCHEMA as MKDIR_SCHEMA, MkdirArgs
from stash.tools.rm import rm_tool, SCHEMA as RM_SCHEMA, RmArgs
from stash.tools.rename import rename_tool, SCHEMA as RENAME_SCHEMA, RenameArgs
from stash.tools.glob import glob_tool, SCHEMA as GLOB_SCHEMA, GlobArgs

ALL_TOOLS = {
    "ls": ls_tool,
    "mv": mv_tool,
    "mkdir": mkdir_tool,
    "rm": rm_tool,
    "rename": rename_tool,
    "glob": glob_tool,
}

ALL_SCHEMAS = [LS_SCHEMA, MV_SCHEMA, MKDIR_SCHEMA, RM_SCHEMA, RENAME_SCHEMA, GLOB_SCHEMA]

ALL_VALIDATORS = {
    "ls": LsArgs,
    "mv": MvArgs,
    "mkdir": MkdirArgs,
    "rm": RmArgs,
    "rename": RenameArgs,
    "glob": GlobArgs,
}
