"""
Tests for all six filesystem tools.

Each test gets a fresh tmp_path directory from pytest. Tests verify both the
return string and the actual filesystem state after the call.
"""

import pytest

from stash.tools.ls import ls_tool
from stash.tools.mv import mv_tool
from stash.tools.mkdir import mkdir_tool
from stash.tools.rm import rm_tool
from stash.tools.rename import rename_tool
from stash.tools.glob import glob_tool


# ---------------------------------------------------------------------------
# ls
# ---------------------------------------------------------------------------

class TestLs:
    def test_lists_files_and_dirs(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello")
        (tmp_path / "subdir").mkdir()
        result = ls_tool(str(tmp_path))
        assert "file.txt" in result
        assert "subdir/" in result

    def test_dirs_listed_before_files(self, tmp_path):
        (tmp_path / "zebra.txt").write_text("")
        (tmp_path / "alpha").mkdir()
        result = ls_tool(str(tmp_path))
        lines = result.splitlines()
        assert lines[0] == "alpha/"
        assert lines[1] == "zebra.txt"

    def test_empty_directory(self, tmp_path):
        assert ls_tool(str(tmp_path)) == "(empty)"

    def test_nonexistent_path(self, tmp_path):
        result = ls_tool(str(tmp_path / "ghost"))
        assert result.startswith("error:")
        assert "does not exist" in result

    def test_file_instead_of_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        result = ls_tool(str(f))
        assert result.startswith("error:")
        assert "not a directory" in result


# ---------------------------------------------------------------------------
# mv
# ---------------------------------------------------------------------------

class TestMv:
    def test_moves_file(self, tmp_path):
        src = tmp_path / "a.txt"
        dst = tmp_path / "b.txt"
        src.write_text("content")
        result = mv_tool(str(src), str(dst))
        assert "moved" in result
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "content"

    def test_moves_directory(self, tmp_path):
        src = tmp_path / "old_dir"
        src.mkdir()
        (src / "nested.txt").write_text("hi")
        dst = tmp_path / "new_dir"
        result = mv_tool(str(src), str(dst))
        assert "moved" in result
        assert not src.exists()
        assert (dst / "nested.txt").exists()

    def test_moves_into_existing_directory(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("data")
        dest_dir = tmp_path / "archive"
        dest_dir.mkdir()
        dst = dest_dir / "file.txt"
        result = mv_tool(str(src), str(dst))
        assert "moved" in result
        assert dst.exists()

    def test_nonexistent_source(self, tmp_path):
        result = mv_tool(str(tmp_path / "ghost.txt"), str(tmp_path / "b.txt"))
        assert result.startswith("error:")
        assert "does not exist" in result

    def test_destination_already_exists(self, tmp_path):
        src = tmp_path / "a.txt"
        dst = tmp_path / "b.txt"
        src.write_text("a")
        dst.write_text("b")
        result = mv_tool(str(src), str(dst))
        assert result.startswith("error:")
        assert "already exists" in result
        assert src.exists()  # source untouched


# ---------------------------------------------------------------------------
# mkdir
# ---------------------------------------------------------------------------

class TestMkdir:
    def test_creates_directory(self, tmp_path):
        new_dir = tmp_path / "new"
        result = mkdir_tool(str(new_dir))
        assert "created" in result
        assert new_dir.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        result = mkdir_tool(str(nested))
        assert "created" in result
        assert nested.is_dir()

    def test_already_exists_is_silent(self, tmp_path):
        """exist_ok=True means creating an existing dir is not an error."""
        existing = tmp_path / "exists"
        existing.mkdir()
        result = mkdir_tool(str(existing))
        assert "created" in result
        assert existing.is_dir()


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------

class TestRm:
    def test_deletes_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("bye")
        result = rm_tool(str(f))
        assert "deleted" in result
        assert not f.exists()

    def test_nonexistent_file(self, tmp_path):
        result = rm_tool(str(tmp_path / "ghost.txt"))
        assert result.startswith("error:")
        assert "does not exist" in result

    def test_refuses_to_delete_directory(self, tmp_path):
        d = tmp_path / "mydir"
        d.mkdir()
        result = rm_tool(str(d))
        assert result.startswith("error:")
        assert "will not delete a directory" in result
        assert d.exists()  # directory untouched


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

class TestRename:
    def test_renames_file(self, tmp_path):
        f = tmp_path / "old.txt"
        f.write_text("data")
        result = rename_tool(str(f), "new.txt")
        assert "renamed" in result
        assert not f.exists()
        assert (tmp_path / "new.txt").exists()

    def test_renames_directory(self, tmp_path):
        d = tmp_path / "old_name"
        d.mkdir()
        result = rename_tool(str(d), "new_name")
        assert "renamed" in result
        assert not d.exists()
        assert (tmp_path / "new_name").is_dir()

    def test_stays_in_same_parent(self, tmp_path):
        """new_name is just a name, not a path — file stays in the same directory."""
        sub = tmp_path / "sub"
        sub.mkdir()
        f = sub / "file.txt"
        f.write_text("hi")
        rename_tool(str(f), "renamed.txt")
        assert (sub / "renamed.txt").exists()
        assert not (tmp_path / "renamed.txt").exists()

    def test_nonexistent_path(self, tmp_path):
        result = rename_tool(str(tmp_path / "ghost.txt"), "new.txt")
        assert result.startswith("error:")
        assert "does not exist" in result

    def test_destination_already_exists(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("a")
        (tmp_path / "b.txt").write_text("b")
        result = rename_tool(str(f), "b.txt")
        assert result.startswith("error:")
        assert "already exists" in result
        assert f.exists()  # source untouched


# ---------------------------------------------------------------------------
# glob
# ---------------------------------------------------------------------------

class TestGlob:
    def test_matches_by_extension(self, tmp_path):
        (tmp_path / "a.txt").write_text("")
        (tmp_path / "b.txt").write_text("")
        (tmp_path / "c.py").write_text("")
        result = glob_tool("*.txt", str(tmp_path))
        assert "a.txt" in result
        assert "b.txt" in result
        assert "c.py" not in result

    def test_recursive_pattern(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.txt").write_text("")
        (tmp_path / "top.txt").write_text("")
        result = glob_tool("**/*.txt", str(tmp_path))
        assert "deep.txt" in result
        assert "top.txt" in result

    def test_no_matches(self, tmp_path):
        (tmp_path / "file.py").write_text("")
        result = glob_tool("*.txt", str(tmp_path))
        assert result == "(no matches)"

    def test_nonexistent_base_path(self, tmp_path):
        result = glob_tool("*.txt", str(tmp_path / "ghost"))
        assert result.startswith("error:")
        assert "does not exist" in result

    def test_default_base_path_uses_home(self):
        """When base_path is omitted, glob runs from the user's home directory."""
        from pathlib import Path
        result = glob_tool("*")
        home = str(Path.home())
        assert home in result or result == "(no matches)"
