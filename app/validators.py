"""Input validation and normalization.

The domain a user submits is used both as a filesystem path (``results/<domain>``)
and as an argument to external tools. Normalizing and strictly validating it here
is what keeps the rest of the app safe from path traversal and command injection,
so every entry point must route user input through :func:`normalize_domain`.
"""
import re


class ValidationError(ValueError):
    """Raised when user-supplied input fails validation."""


# A DNS label: 1-63 chars, letters/digits/hyphen, not starting or ending with a
# hyphen. A domain is two or more labels joined by dots. This character class
# deliberately excludes every shell metacharacter, slash and whitespace, so a
# value that matches cannot inject a command or escape the results directory.
_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
_DOMAIN_RE = re.compile(r"^(?:%s\.)+%s$" % (_LABEL, _LABEL))
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://")
_IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def normalize_domain(raw):
    """Return a clean, validated domain or raise :class:`ValidationError`.

    Accepts common messy input (URLs, trailing dots, ports, surrounding
    whitespace, mixed case) and reduces it to a bare registrable hostname such
    as ``example.com``. Bare IP addresses and single-label hosts are rejected
    because the enumeration step is meaningless for them.
    """
    if raw is None:
        raise ValidationError("A domain is required.")

    domain = raw.strip().lower()
    if not domain:
        raise ValidationError("A domain is required.")

    # Peel away anything that looks like a URL: scheme, credentials, path.
    domain = _SCHEME_RE.sub("", domain)
    domain = domain.rsplit("@", 1)[-1]
    domain = re.split(r"[/?#]", domain, maxsplit=1)[0]
    domain = domain.split(":", 1)[0]  # strip :port
    domain = domain.strip().rstrip(".")

    if not domain:
        raise ValidationError("A domain is required.")
    if len(domain) > 253:
        raise ValidationError("That domain name is too long.")
    if _IPV4_RE.match(domain):
        raise ValidationError(
            "Enter a domain name rather than an IP address."
        )
    if not _DOMAIN_RE.match(domain):
        raise ValidationError(
            "Enter a valid domain name, for example example.com"
        )
    return domain


def is_valid_domain(raw):
    """Boolean convenience wrapper around :func:`normalize_domain`."""
    try:
        normalize_domain(raw)
        return True
    except ValidationError:
        return False
