"""Exception hierarchy for pymodes decoder errors.

All pymodes decode errors inherit from DecodeError, which itself is a
ValueError subclass so users can use `except ValueError:` to catch any
decoder issue. Specific subclasses distinguish the failure mode.
"""


class DecodeError(ValueError):
    """Base class for all pymodes decode errors."""


class InvalidHexError(DecodeError):
    """Raised when the input string contains non-hex characters."""

    def __init__(self, raw: str) -> None:
        super().__init__(f"invalid hex input: {raw!r}")
        self.raw = raw


class InvalidLengthError(DecodeError):
    """Raised when the input has the wrong number of hex characters."""

    def __init__(self, *, actual: int, expected: tuple[int, ...]) -> None:
        exp = " or ".join(str(e) for e in expected)
        super().__init__(f"expected {exp} hex chars, got {actual}")
        self.actual = actual
        self.expected = expected


class UnknownDFError(DecodeError):
    """Raised when the downlink format is not a recognized Mode-S value."""

    def __init__(self, df: int) -> None:
        super().__init__(f"unknown downlink format: {df}")
        self.df = df
