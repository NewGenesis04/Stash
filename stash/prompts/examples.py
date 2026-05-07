"""
Dynamic few-shot examples for the system prompt.
Generates traces using the user's actual home directory to improve path grounding.
"""

def get_examples(home_path: str) -> str:
    # Use forward slashes for cross-platform examples in the prompt
    # but acknowledge the system context block for exact paths.
    h = home_path.rstrip("/").rstrip("\\")
    
    return f"""\
### Example 1 — Folder reference, resolve first
User: What's in my downloads folder?
[Call resolve_location: name="downloads" — returns "{h}/Downloads"]
[Call ls: path="{h}/Downloads"]
Stash: 12 files in Downloads: ...

### Example 2 — Unknown location, picker fires
User: Move all PDFs to my work archive.
[Call resolve_location: name="work archive" — user picks folder, returns "{h}/Work/Archive"]
[Call glob: pattern=**/*.pdf, base_path="{h}/Documents"]
[Call mv: ...]
Stash: Moved 4 PDFs to {h}/Work/Archive.

### Example 3 — Ambiguous task, ask first
User: Sort my downloads folder.
Stash: How would you like them sorted? For example: by file type, by date, or by a
specific naming pattern?

### Example 4 — Error during execution
User: Delete all the .tmp files in my projects folder.
[Call resolve_location: name="projects" — returns "{h}/Projects"]
[Call glob: pattern=**/*.tmp, base_path="{h}/Projects" — returns "(no matches)"]
Stash: No .tmp files found in Projects. Nothing was deleted.\
"""
