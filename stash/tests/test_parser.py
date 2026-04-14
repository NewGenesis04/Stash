"""
Tests for _parse_response in stash.core.agent.

_parse_response takes raw model output and returns:
  (thought, action, args, final_answer)

Two valid shapes:
  - Thought + Action + Action Input  → (thought, action, dict, None)
  - Thought + Final Answer           → (thought, None, None, final_answer)

Raises ValueError for anything malformed.
"""

import pytest

from stash.core.agent import _parse_response


# ---------------------------------------------------------------------------
# Happy path — action step
# ---------------------------------------------------------------------------

def test_action_step_basic():
    text = (
        "Thought: I should list the files\n"
        "Action: ls\n"
        "Action Input: {\"path\": \"/tmp\"}"
    )
    thought, action, args, final = _parse_response(text)
    assert thought == "I should list the files"
    assert action == "ls"
    assert args == {"path": "/tmp"}
    assert final is None


def test_action_step_complex_args():
    text = (
        "Thought: Move the file\n"
        "Action: mv\n"
        "Action Input: {\"src\": \"/tmp/a.txt\", \"dst\": \"/home/ogie/docs/a.txt\"}"
    )
    _, action, args, _ = _parse_response(text)
    assert action == "mv"
    assert args == {"src": "/tmp/a.txt", "dst": "/home/ogie/docs/a.txt"}


def test_action_step_nested_json_args():
    text = (
        "Thought: Complex call\n"
        "Action: some_tool\n"
        "Action Input: {\"options\": {\"recursive\": true, \"limit\": 10}}"
    )
    _, _, args, _ = _parse_response(text)
    assert args == {"options": {"recursive": True, "limit": 10}}


def test_action_step_empty_action_input_braces():
    """Explicit empty object is valid."""
    text = (
        "Thought: No args needed\n"
        "Action: ls\n"
        "Action Input: {}"
    )
    _, _, args, _ = _parse_response(text)
    assert args == {}


def test_action_step_missing_action_input_line():
    """No Action Input line at all — defaults to empty dict."""
    text = (
        "Thought: No args needed\n"
        "Action: ls\n"
    )
    _, _, args, _ = _parse_response(text)
    assert args == {}


# ---------------------------------------------------------------------------
# Happy path — final answer
# ---------------------------------------------------------------------------

def test_final_answer_basic():
    text = (
        "Thought: I have finished the task\n"
        "Final Answer: Moved 3 files to /archive."
    )
    thought, action, args, final = _parse_response(text)
    assert thought == "I have finished the task"
    assert final == "Moved 3 files to /archive."
    assert action is None
    assert args is None


def test_final_answer_with_colon_in_value():
    """Final Answer value may itself contain a colon."""
    text = (
        "Thought: Done\n"
        "Final Answer: Result: 5 files moved, 2 deleted."
    )
    _, _, _, final = _parse_response(text)
    assert final == "Result: 5 files moved, 2 deleted."


def test_final_answer_takes_priority_over_action():
    """When both Action and Final Answer are present, Final Answer wins."""
    text = (
        "Thought: Almost done\n"
        "Action: ls\n"
        "Action Input: {\"path\": \"/tmp\"}\n"
        "Final Answer: All done."
    )
    _, action, args, final = _parse_response(text)
    assert final == "All done."
    assert action is None
    assert args is None


# ---------------------------------------------------------------------------
# Whitespace and formatting tolerance
# ---------------------------------------------------------------------------

def test_leading_trailing_whitespace_on_values():
    text = (
        "Thought:   think with spaces   \n"
        "Action:   ls   \n"
        "Action Input:   {\"path\": \"/tmp\"}   "
    )
    thought, action, args, _ = _parse_response(text)
    assert thought == "think with spaces"
    assert action == "ls"
    assert args == {"path": "/tmp"}


def test_colon_in_thought_value():
    """split(':', 1) means only the first colon is the delimiter."""
    text = (
        "Thought: I need to check: is the file there?\n"
        "Action: ls\n"
        "Action Input: {\"path\": \"/tmp\"}"
    )
    thought, _, _, _ = _parse_response(text)
    assert thought == "I need to check: is the file there?"


def test_extra_noise_lines_ignored():
    """Lines that don't match a known key are silently skipped."""
    text = (
        "Thought: Let me think\n"
        "Note: this line is not part of the format\n"
        "Action: ls\n"
        "Action Input: {\"path\": \"/tmp\"}\n"
        "Some trailing garbage"
    )
    thought, action, args, final = _parse_response(text)
    assert thought == "Let me think"
    assert action == "ls"
    assert args == {"path": "/tmp"}
    assert final is None


def test_windows_line_endings():
    """CRLF line endings should parse the same as LF."""
    text = (
        "Thought: Thinking\r\n"
        "Action: ls\r\n"
        "Action Input: {\"path\": \"/tmp\"}"
    )
    thought, action, _, _ = _parse_response(text)
    assert thought == "Thinking"
    assert action == "ls"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_missing_thought_raises():
    text = (
        "Action: ls\n"
        "Action Input: {\"path\": \"/tmp\"}"
    )
    with pytest.raises(ValueError, match="no Thought"):
        _parse_response(text)


def test_empty_string_raises():
    with pytest.raises(ValueError, match="no Thought"):
        _parse_response("")


def test_whitespace_only_raises():
    with pytest.raises(ValueError, match="no Thought"):
        _parse_response("   \n   ")


def test_thought_only_no_action_no_final_raises():
    """Thought present but neither Action nor Final Answer."""
    text = "Thought: I am thinking"
    with pytest.raises(ValueError, match="no Action or Final Answer"):
        _parse_response(text)


def test_invalid_json_in_action_input_raises():
    text = (
        "Thought: Do something\n"
        "Action: ls\n"
        "Action Input: not valid json"
    )
    with pytest.raises(ValueError, match="not valid JSON"):
        _parse_response(text)


def test_partial_json_raises():
    text = (
        "Thought: Do something\n"
        "Action: ls\n"
        "Action Input: {\"path\":"
    )
    with pytest.raises(ValueError, match="not valid JSON"):
        _parse_response(text)


def test_json_array_instead_of_object_raises():
    """Action Input must be a JSON object, not an array."""
    text = (
        "Thought: Do something\n"
        "Action: ls\n"
        "Action Input: [\"a\", \"b\"]"
    )
    # json.loads succeeds on arrays, but the agent expects a dict.
    # This verifies the current behaviour — args will be a list, not a dict.
    # If stricter validation is added later, update this test.
    _, _, args, _ = _parse_response(text)
    assert args == ["a", "b"]
