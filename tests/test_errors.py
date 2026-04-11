"""Tests for pyModeS.errors exception hierarchy."""

import pytest

from pyModeS.errors import (
    DecodeError,
    InvalidHexError,
    InvalidLengthError,
    UnknownDFError,
)


def test_all_errors_inherit_from_decode_error():
    assert issubclass(InvalidHexError, DecodeError)
    assert issubclass(InvalidLengthError, DecodeError)
    assert issubclass(UnknownDFError, DecodeError)


def test_decode_error_inherits_from_value_error():
    # DecodeError is a ValueError so users can catch either one
    assert issubclass(DecodeError, ValueError)


def test_invalid_hex_error_message():
    err = InvalidHexError("XYZ")
    assert "XYZ" in str(err)
    assert "invalid hex" in str(err).lower()


def test_invalid_length_error_message():
    err = InvalidLengthError(actual=10, expected=(14, 28))
    assert "10" in str(err)
    assert "14" in str(err) or "28" in str(err)


def test_unknown_df_error_message():
    err = UnknownDFError(99)
    assert "99" in str(err)


def test_raise_and_catch_as_value_error():
    # Users should be able to catch DecodeError via ValueError
    with pytest.raises(ValueError):
        raise InvalidHexError("abc")
