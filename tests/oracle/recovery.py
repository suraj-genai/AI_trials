"""Recover the committed key-value table from a crashed journal.

The recovery repeats history from the start of the durable log against the last
checkpoint's snapshot, replays the updates of committed transactions only, and
skips any update already reflected in the snapshot.
"""

from wal import durable_prefix

UPDATE_OPS = ("set", "add", "del")


def recover(lines):
    records = durable_prefix(lines)

    # A transaction is committed only if its commit record is durable: a commit
    # that lands in the residue past the durable log does not commit anything.
    committed = {r["txn"] for r in records if r["op"] == "commit"}

    # Start from the last durable checkpoint's snapshot. Each snapshot entry is
    # (value, applied_lsn): the lsn of the last update already reflected in it.
    table, applied = {}, {}
    checkpoints = [r for r in records if r["op"] == "checkpoint"]
    if checkpoints:
        for key, (value, applied_lsn) in checkpoints[-1]["state"].items():
            table[key] = value
            applied[key] = applied_lsn

    # Repeat history from the START of the durable log -- not from the
    # checkpoint -- so a transaction whose updates precede the checkpoint but
    # whose commit follows it is not lost. Skip an update already in the
    # snapshot (lsn <= the key's applied lsn), so a durable update reflected in
    # the checkpoint is not applied a second time.
    for record in sorted((r for r in records if r["op"] in UPDATE_OPS),
                         key=lambda r: r["lsn"]):
        if record["txn"] not in committed:
            continue
        if record["lsn"] <= applied.get(record["key"], 0):
            continue
        op = record["op"]
        if op == "set":
            table[record["key"]] = record["value"]
        elif op == "add":
            # An add to a key with no value yet treats the missing value as 0.
            table[record["key"]] = table.get(record["key"], 0) + record["delta"]
        else:  # del
            table.pop(record["key"], None)
        applied[record["key"]] = record["lsn"]

    return {key: value for key, value in table.items()}
