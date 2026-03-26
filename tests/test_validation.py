"""Tests for entry name validation and input sanitization."""


from passclip import validate_entry_name


def _is_valid(name: str) -> bool:
    """Helper — validate_entry_name returns (bool, msg) or just bool depending on version."""
    result = validate_entry_name(name)
    if isinstance(result, tuple):
        return result[0]
    return bool(result)


class TestValidateEntryName:
    """Entry names must be safe for filesystem paths and pass commands."""

    def test_simple_name(self):
        assert _is_valid("email/gmail")

    def test_nested_path(self):
        assert _is_valid("web/social/twitter")

    def test_rejects_empty(self):
        assert not _is_valid("")

    def test_rejects_path_traversal(self):
        assert not _is_valid("../etc/passwd")
        assert not _is_valid("foo/../../bar")

    def test_rejects_dotdot_component(self):
        assert not _is_valid("foo/../bar")

    def test_rejects_leading_dash(self):
        assert not _is_valid("-rf")

    def test_rejects_leading_slash(self):
        assert not _is_valid("/etc/passwd")

    def test_rejects_null_byte(self):
        assert not _is_valid("foo\x00bar")

    def test_rejects_control_chars(self):
        assert not _is_valid("foo\nbar")
        assert not _is_valid("foo\tbar")

    def test_rejects_backslash(self):
        assert not _is_valid("foo\\bar")

    def test_rejects_shell_metacharacters(self):
        for char in ("|", ";", "&", "$", "`", "(", ")", "{", "}", "<", ">"):
            assert not _is_valid(f"foo{char}bar"), f"Should reject '{char}'"

    def test_allows_dots_in_name(self):
        assert _is_valid("web/example.com")

    def test_allows_hyphens_and_underscores(self):
        assert _is_valid("web/my-site_v2")

    def test_allows_spaces(self):
        assert _is_valid("web/my site")
