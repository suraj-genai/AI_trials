"""Journal record format: parse a durable line, and find the durable prefix.

A record on disk is one JSON line ``{"crc": <uint32>, "r": <payload>}``. See
/app/data/WAL_FORMAT.md for the record layout and the recovery rules.
"""

import json
import zlib


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def crc_of(payload):
    """Unsigned 32-bit CRC of a record payload's canonical form."""
    return zlib.crc32(_canonical(payload)) & 0xFFFFFFFF


def parse_line(line):
    """Return the record payload for a line, or None if it does not parse."""
    line = line.rstrip("\n")
    if not line:
        return None
    try:
        obj = json.loads(line)
    except Exception:
        return None
    if not isinstance(obj, dict) or "r" not in obj:
        return None
    payload = obj["r"]
    if not isinstance(payload, dict):
        return None
    return payload


def durable_prefix(lines):
    """Every record the journal parses, in order."""
    out = []
    for line in lines:
        record = parse_line(line)
        if record is None:
            continue
        out.append(record)
    return out
