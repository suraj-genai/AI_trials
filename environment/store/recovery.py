"""Recover the committed key-value table from a crashed journal.
"""

from wal import durable_prefix, parse_line


UPDATE_OPS = ("set", "add", "del")


def recover(lines):
    records = durable_prefix(lines)

    committed = set()
    commit_lsn = {}
    for line in lines:
        record = parse_line(line)
        if record is not None and record.get("op") == "commit":
            committed.add(record["txn"])
            commit_lsn[record["txn"]] = record["lsn"]

    table, applied, checkpoint_lsn = {}, {}, -1
    checkpoints = [r for r in records if r["op"] == "checkpoint"]
    if checkpoints:
        for key, (value, applied_lsn) in checkpoints[-1]["state"].items():
            table[key] = value
            applied[key] = applied_lsn
        checkpoint_lsn = checkpoints[-1]["lsn"]

    for record in sorted(
        (r for r in records if r["op"] in UPDATE_OPS),
        key=lambda r: r["lsn"],
    ):
        txn = record["txn"]
        if txn not in committed:
            continue

        if commit_lsn.get(txn, checkpoint_lsn + 1) <= checkpoint_lsn:
            continue
        if record["lsn"] <= checkpoint_lsn:
            continue

        op = record["op"]
        key = record["key"]
        if op == "set":
            table[key] = record["value"]
        elif op == "add":
            if key in table:
                table[key] += record["delta"]
        else:
            table.pop(key, None)

    return {key: value for key, value in table.items()}
