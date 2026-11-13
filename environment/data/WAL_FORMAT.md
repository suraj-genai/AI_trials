# Journal format and recovery

The store keeps a table of integer-valued keys. Every change is written to an append-only journal before it is applied, and after a crash the committed table is rebuilt from that journal. This document is the authority on the journal layout and on the semantics recovery must preserve; where the shipped build and this document disagree, the build is what is wrong.

## Records

The journal is one preallocated file, `journal.log`, holding one record per line. A line is a JSON object with two members:

```text
{"crc": <unsigned 32-bit integer>, "r": <payload>}
```

`crc` is `zlib.crc32` of the payload's **canonical form** — the payload serialized as JSON with its keys in sorted order and no whitespace, `json.dumps(payload, sort_keys=True, separators=(",", ":"))`, encoded UTF-8 — taken as an unsigned 32-bit integer.

Every payload has an integer `lsn` (log sequence number) and an `op`. The `lsn` strictly increases in the order records were written. The record types are:

| `op`         | other fields          | meaning                                        |
| ------------ | --------------------- | ---------------------------------------------- |
| `begin`      | `txn`                 | transaction `txn` starts                       |
| `set`        | `txn`, `key`, `value` | within `txn`, set `key` to the integer `value` |
| `add`        | `txn`, `key`, `delta` | within `txn`, add the integer `delta` to `key` |
| `del`        | `txn`, `key`          | within `txn`, remove `key`                     |
| `commit`     | `txn`                 | `txn` commits                                  |
| `abort`      | `txn`                 | `txn` aborts                                   |
| `checkpoint` | `state`               | a snapshot (below)                             |

## The durable log — rule `durable_prefix`

`journal.log` is preallocated and reused across runs, so a crash can leave a half-written record, and behind it the bytes of an earlier, longer epoch. The **durable log** is the run of records from the start of the file up to, but not including, the first line that either does not parse as a complete record or whose `crc` does not match its payload. That line marks where this epoch's writing stopped; it and every line after it are residue from an earlier epoch and are **not** part of the log. Recovery must use only this durable portion.

## Commit — rule `commit_durability`

A transaction's updates take effect only if the transaction **committed**: its `commit` record is present **within the durable log**. A transaction that aborted, or that has no `commit`, is uncommitted and none of its updates are applied. `commit_durability`: a `commit` that falls in the residue past the durable log is not durable and does not commit its transaction.

## Checkpoints

A `checkpoint` record carries `state`, a snapshot of the committed table as of that checkpoint. Each entry is:

```text
"<key>": [<value>, <applied_lsn>]
```

The snapshot is a representation of committed state at a particular point in the journal. `applied_lsn` records the journal position associated with the version represented by that entry.

Recovery uses the snapshot associated with the last checkpoint in the durable log. If the durable log contains no checkpoint, the starting table is empty.

## Redo — rules `redo_pass` and `add_missing`

The durable portion of the journal is the authoritative history from which the final committed table is reconstructed.

A fuzzy checkpoint may omit updates belonging to transactions that were still uncommitted when the checkpoint was taken. Recovery must therefore account for the complete durable history of every transaction that ultimately commits.

The recovered result must preserve effects already represented by the selected checkpoint while also applying committed effects that are not represented there.

`redo_pass`: replay must be idempotent. Reapplying history already represented by the starting state must not change the recovered result, while committed history not represented there must still take effect.

When a committed update does need to take effect:

* `set` sets the key to `value`.
* `del` removes the key.
* `add` adds `delta` to the key's current value.
* `add_missing`: an `add` against a key with no current value creates that key, using zero as the starting value.

The recovered table is every key still present, with its integer value.

## Rule vocabulary

The rules named above form a closed vocabulary. Any defect identified in the implementation must be categorized strictly using one of these rules:

`durable_prefix`, `commit_durability`, `redo_pass`, `add_missing`.
