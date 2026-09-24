"""Shared helpers for the scanner packages."""


class ScannerError(RuntimeError):
    """Raised when an external scan tool is missing or fails.

    The message is safe to surface to the user: it explains what went wrong
    (a missing binary, a non-zero exit) without leaking internal details.
    """
