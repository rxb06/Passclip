"""Regression tests for the clipboard-clear rework (security review L5, L6, L7).

- L5: the secret travels to the clear child over a stdin pipe, never env/argv
- L6: the native fallback verifies clipboard content before clearing
- L7: the clear strategy is keyed on how the copy actually happened
"""

import subprocess
import sys
import types
from unittest.mock import patch

import passclip
from passclip import _spawn_clipboard_clear, copy_to_clipboard

PASTE_HELPER = (
    "import sys\nwith open(sys.argv[1], 'rb') as f:\n    sys.stdout.buffer.write(f.read())\n"
)
COPY_HELPER = (
    "import sys\n"
    "data = sys.stdin.buffer.read()\n"
    "with open(sys.argv[1], 'wb') as f:\n"
    "    f.write(data)\n"
)


def _run_native_clear(tmp_path, clipboard_now, copied_text, paste_target=None):
    """Run the native clear script with fake paste/copy tools backed by a file."""
    state = tmp_path / "state.bin"
    state.write_bytes(clipboard_now)
    paste_py = tmp_path / "paste.py"
    paste_py.write_text(PASTE_HELPER)
    copy_py = tmp_path / "copy.py"
    copy_py.write_text(COPY_HELPER)
    script = passclip._NATIVE_CLEAR_SCRIPT.format(
        copy_cmd=[sys.executable, str(copy_py), str(state)],
        paste_cmd=[sys.executable, str(paste_py), str(paste_target or state)],
    )
    subprocess.run(
        [sys.executable, "-c", script],
        env={"_PASSCLIP_CLIP_TIMEOUT": "0"},
        input=copied_text.encode("utf-8"),
        timeout=30,
        check=True,
    )
    return state.read_bytes()


class TestNativeClearScript:
    """L6 — native fallback compares before clearing."""

    def test_matching_content_is_cleared(self, tmp_path):
        assert _run_native_clear(tmp_path, b"hunter2", "hunter2") == b""

    def test_trailing_newline_still_matches(self, tmp_path):
        assert _run_native_clear(tmp_path, b"hunter2\n", "hunter2") == b""

    def test_non_ascii_secret_is_cleared(self, tmp_path):
        assert _run_native_clear(tmp_path, "pässwörd".encode(), "pässwörd") == b""

    def test_unrelated_content_is_preserved(self, tmp_path):
        assert _run_native_clear(tmp_path, b"user copied this", "hunter2") == b"user copied this"

    def test_unreadable_clipboard_clears_fail_safe(self, tmp_path):
        """If the paste tool fails, clear anyway — fail safe for the secret."""
        missing = tmp_path / "does-not-exist"
        assert _run_native_clear(tmp_path, b"whatever", "hunter2", paste_target=missing) == b""


class TestSpawnTransport:
    """L5 — the secret must never appear in the child's environment."""

    def test_secret_passed_via_stdin_not_env(self):
        with patch("passclip.subprocess.Popen") as popen:
            child = popen.return_value
            _spawn_clipboard_clear("s3cret-value", 1, "pyperclip")
        assert popen.call_args.kwargs["stdin"] is subprocess.PIPE
        env = popen.call_args.kwargs["env"]
        assert all("s3cret-value" not in str(v) for v in env.values())
        child.stdin.write.assert_called_once_with(b"s3cret-value")
        child.stdin.close.assert_called_once()

    def test_unknown_mechanism_spawns_nothing(self):
        with patch("passclip.subprocess.Popen") as popen:
            _spawn_clipboard_clear("x", 1, "not-a-real-tool")
        popen.assert_not_called()


class TestMechanismKeying:
    """L7 — the clearer must match the mechanism that actually copied."""

    def test_broken_pyperclip_backend_falls_back_to_native_clear(self):
        fake = types.ModuleType("pyperclip")
        fake.copy = lambda text: (_ for _ in ()).throw(RuntimeError("no backend"))
        with (
            patch.dict(sys.modules, {"pyperclip": fake}),
            patch.dict("passclip.DEPS", {"pyperclip": True}),
            patch(
                "passclip.shutil.which",
                side_effect=lambda t: "/usr/bin/x" if t == "pbcopy" else None,
            ),
            patch("passclip.subprocess.run"),
            patch("passclip._spawn_clipboard_clear") as spawn,
        ):
            assert copy_to_clipboard("s3cret", timeout=1) is True
        spawn.assert_called_once()
        assert spawn.call_args.args[2] == "pbcopy"

    def test_working_pyperclip_uses_pyperclip_clear(self):
        fake = types.ModuleType("pyperclip")
        fake.copy = lambda text: None
        with (
            patch.dict(sys.modules, {"pyperclip": fake}),
            patch.dict("passclip.DEPS", {"pyperclip": True}),
            patch("passclip._spawn_clipboard_clear") as spawn,
        ):
            assert copy_to_clipboard("s3cret", timeout=1) is True
        spawn.assert_called_once()
        assert spawn.call_args.args[2] == "pyperclip"

    def test_no_tool_at_all_reports_failure(self):
        with (
            patch.dict("passclip.DEPS", {"pyperclip": False}),
            patch("passclip.shutil.which", return_value=None),
            patch("passclip._spawn_clipboard_clear") as spawn,
        ):
            assert copy_to_clipboard("s3cret", timeout=1) is False
        spawn.assert_not_called()
