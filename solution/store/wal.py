"""Journal record format: parse a durable line, and find the durable prefix.

A record on disk is one JSON line ``{"crc": <uint32>, "r": <payload>}``. The
checksum covers the payload's canonical form -- its fields serialized as JSON
with sorted keys and no whitespace -- and nothing else. A line is a durable
record only if it parses and its stored checksum matches; the first line that
fails either test ends this epoch's durable log (everything after it is residue
from an earlier use of the preallocated file).
"""

import json
import zlib


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def crc_of(payload):
    """Unsigned 32-bit CRC of a record payload's canonical form."""
    return zlib.crc32(_canonical(payload)) & 0xFFFFFFFF


def parse_line(line):
    """Return the record payload if `line` is a well-formed, checksum-valid
    record; return None if it is unparsable or its checksum does not match."""
    line = line.rstrip("\n")
    if not line:
        return None
    try:
        obj = json.loads(line)
    except Exception:
        return None
    if not isinstance(obj, dict) or "r" not in obj or "crc" not in obj:
        return None
    payload = obj["r"]
    if not isinstance(payload, dict):
        return None
    try:
        expected = crc_of(payload)
    except Exception:
        return None
    if obj["crc"] != expected:
        return None
    return payload


def durable_prefix(lines):
    """The records up to, but not including, the first line that fails to parse
    or fails its checksum. Everything at and after that line is not part of the
    durable log."""
    out = []
    for line in lines:
        record = parse_line(line)
        if record is None:
            break
        out.append(record)
    return out
