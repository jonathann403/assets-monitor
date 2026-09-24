import pytest

from app.validators import ValidationError, is_valid_domain, normalize_domain


@pytest.mark.parametrize("raw,expected", [
    ("example.com", "example.com"),
    ("  Example.COM  ", "example.com"),
    ("https://www.example.com/path?q=1", "www.example.com"),
    ("http://user:pass@host.example.com:8443/x", "host.example.com"),
    ("sub.example.co.uk.", "sub.example.co.uk"),
    ("xn--80ak6aa92e.com", "xn--80ak6aa92e.com"),
    ("foo.com/../bar", "foo.com"),  # path stripped -> safe bare host
])
def test_normalize_accepts_and_cleans(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "   ", None,
    "localhost", "com", "a..com", "-lead.com", "trail-.com",
    "exa mple.com",
    "127.0.0.1",                    # bare IP rejected
    "a.com; rm -rf /",             # shell metacharacters
    "a.com && curl evil",
    "$(whoami).example.com",
    "`id`.com",
    "a.com|nc -e",
    "../../../etc/passwd",
])
def test_normalize_rejects_bad_and_dangerous(raw):
    with pytest.raises(ValidationError):
        normalize_domain(raw)


def test_normalized_output_has_no_shell_metacharacters():
    # Whatever passes must be composed only of label chars and dots.
    for raw in ["example.com", "https://a.b.c.example.io/x", "WWW.Example.Org"]:
        out = normalize_domain(raw)
        assert all(c.isalnum() or c in ".-" for c in out)


def test_is_valid_domain():
    assert is_valid_domain("example.com") is True
    assert is_valid_domain("nope") is False
