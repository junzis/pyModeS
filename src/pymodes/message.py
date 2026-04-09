"""Message base class and DecodedMessage return type for pymodes v3.

This module defines two public types:

- DecodedMessage: the dict subclass returned by decode() calls. Adds
  attribute access and a to_json() helper while behaving as a plain
  dict for json.dumps, pandas, iteration, and all dict operations.

- Message: the canonical internal representation of a Mode-S message.
  Holds a single int (56 or 112 bits) and exposes lazy cached_property
  accessors for df, icao, crc, typecode. Dispatches to decoder classes
  via decode().

(Message is added in a follow-up task.)
"""

from __future__ import annotations

import json
from typing import Any


class DecodedMessage(dict[str, Any]):
    """A decoded Mode-S message.

    Behaves as a plain dict in every way that matters: JSON-serializable
    via `json.dumps`, works with `pd.DataFrame([msg1, msg2, ...])`,
    iterable, unpackable via `**`, supports `.get("key")` for missing keys.

    Adds attribute access as a convenience:
        msg["typecode"]  # standard dict access
        msg.typecode     # attribute access — equivalent

    Missing-key semantics differ by access style:
        msg.get("foo")     # → None (safe lookup)
        msg["foo"]         # → KeyError (dict semantics)
        msg.foo            # → AttributeError (attribute semantics)
    """

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize to a JSON string.

        Uses `default=str` as a defensive fallback for any
        non-JSON-native value, but every pymodes-decoded field is
        already JSON-native (int, float, str, bool, None, list, dict).
        """
        return json.dumps(self, indent=indent, default=str)
