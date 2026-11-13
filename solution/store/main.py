"""Driver: recover the store from its journal and write the results.

Reads ``<data_dir>/journal.log``, recovers the committed table, and writes:

  <output_dir>/state.json    the recovered table, a JSON object {key: int}
  <output_dir>/findings.json {"rules": [...]}, the recovery rules the shipped
                             build got wrong, named from the fixed vocabulary
                             in WAL_FORMAT.md.
"""

import json
import os

from recovery import recover

# The recovery rules the shipped build violated, named from WAL_FORMAT.md's
# closed vocabulary. This corrected build honours all of them.
FINDINGS = [
    "add_missing",
    "commit_durability",
    "durable_prefix",
    "redo_pass",
]


def _read_journal(data_dir):
    path = os.path.join(data_dir, "journal.log")
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().splitlines()


def main(data_dir=None, output_dir=None):
    if data_dir is None:
        data_dir = "/app/data"
    if output_dir is None:
        output_dir = "/app/output"
    os.makedirs(output_dir, exist_ok=True)

    lines = _read_journal(data_dir)
    state = recover(lines)

    with open(os.path.join(output_dir, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)
    with open(os.path.join(output_dir, "findings.json"), "w", encoding="utf-8") as fh:
        json.dump({"rules": sorted(FINDINGS)}, fh, sort_keys=True)


if __name__ == "__main__":
    main()
