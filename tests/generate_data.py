#!/usr/bin/env python3
"""Synthetic journals for the crash-recovery task.

A journal is one file, ``journal.log``, of one JSON record per line. Records are
``{"crc": <uint32>, "r": <payload>}``; the checksum covers the payload's
canonical form. The generator is the single source of truth for the format and
is used both to draw the held-out graded windows at verify time and (through
solution/build_corpus.py) to lay down the shipped samples.

Windows come in three shapes:

  sample   a clean window: every checkpoint is empty or carries only pre-epoch
           keys the log never touches, no transaction straddles a checkpoint,
           and there is no corruption. None of the recovery edges appears.
  live     the image's own crashed journal -- a clean window, no report.
  graded   held-out. Every edge at once: a torn write mid-log with residue
           behind it, a commit stranded in that residue, a fuzzy checkpoint
           with transactions straddling it, a committed add already in the
           snapshot, an add that creates its key, and delete cases.

Usage:
    python3 generate_data.py <output_dir> <seed> [mode]
"""

import json
import os
import random
import sys
import zlib


# ---- format ---------------------------------------------------------------
def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def crc_of(payload):
    return zlib.crc32(_canonical(payload)) & 0xFFFFFFFF


def encode_record(payload):
    return json.dumps({"crc": crc_of(payload), "r": payload},
                      sort_keys=True, separators=(",", ":"))


def corrupt_line(payload):
    bad = (crc_of(payload) ^ 0x5A5A5A5A) & 0xFFFFFFFF
    return json.dumps({"crc": bad, "r": payload},
                      sort_keys=True, separators=(",", ":"))


def _torn_tail():
    return '{"crc": 40213, "r": {"op": "set", "txn": 90001, "ke'


# ---- generator ------------------------------------------------------------
class Gen:
    def __init__(self, seed):
        # Held-out journals must be reproducible for a given integer of the seed value.
        self.rng = random.Random(int(seed))

        self.lsn = 0
        self.recs = []
        self.used_keys = set()

    def _next_lsn(self):
        self.lsn += 1
        return self.lsn

    def key(self):
        while True:
            k = "%08x" % self.rng.getrandbits(32)
            if k not in self.used_keys:
                self.used_keys.add(k)
                return k

    def emit(self, payload):
        payload = dict(payload)
        payload["lsn"] = self._next_lsn()
        self.recs.append(payload)
        return payload

    def commit(self, txn):
        self.emit({"op": "commit", "txn": txn})

    def abort(self, txn):
        self.emit({"op": "abort", "txn": txn})

    def checkpoint(self, extra_state=None):
        table, applied = {}, {}
        committed = {r["txn"] for r in self.recs if r["op"] == "commit"}

        for r in sorted(
            (x for x in self.recs if x["op"] in ("set", "add", "del")),
            key=lambda x: x["lsn"],
        ):
            if r["txn"] not in committed:
                continue

            if r["op"] == "set":
                table[r["key"]] = r["value"]
            elif r["op"] == "add":
                table[r["key"]] = table.get(r["key"], 0) + r["delta"]
            else:
                table.pop(r["key"], None)

            applied[r["key"]] = r["lsn"]

        state = {k: [v, applied[k]] for k, v in table.items()}

        if extra_state:
            state.update(extra_state)

        self.emit({"op": "checkpoint", "state": state})

    def checkpoint_explicit(self, state):
        self.emit({"op": "checkpoint", "state": state})

    def lines(self):
        return [encode_record(r) for r in self.recs]


# ---- graded window: every edge present ------------------------------------
def build_graded(seed):
    g = Gen(seed)
    r = g.rng
    tid = 1000

    census = {
        "guard": 0,
        "straddle": 0,
        "addmiss": 0,
        "x_loser": 0,
        "delete": 0,
        "delete_existing": 0,
        "delete_uncommitted": 0,
        "residue": 2,
    }

    for _ in range(20):
        tid += 1
        k = g.key()
        g.emit({"op": "begin", "txn": tid})
        g.emit({
            "op": "add",
            "txn": tid,
            "key": k,
            "delta": r.randint(2, 40),
        })
        g.commit(tid)
        census["guard"] += 1

    for _ in range(40):
        tid += 1
        g.emit({"op": "begin", "txn": tid})

        for _ in range(r.randint(1, 3)):
            k = g.key()
            g.emit({
                "op": "set",
                "txn": tid,
                "key": k,
                "value": r.randint(-80, 80),
            })

            if r.random() < 0.5:
                g.emit({
                    "op": "add",
                    "txn": tid,
                    "key": k,
                    "delta": r.randint(1, 25),
                })

        g.commit(tid)

    straddle_snapshot_keys = [g.key() for _ in range(10)]
    straddle_snapshot = {
        k: [r.randint(10, 100), 0]
        for k in straddle_snapshot_keys
    }


    straddle = []
    for i, existing_key in enumerate(straddle_snapshot_keys):
        tid += 1
        g.emit({"op": "begin", "txn": tid})

        g.emit({
            "op": "add",
            "txn": tid,
            "key": existing_key,
            "delta": r.randint(3, 30),
        })
        census["straddle"] += 1

        fresh_key = g.key()
        g.emit({
            "op": "set",
            "txn": tid,
            "key": fresh_key,
            "value": r.randint(1, 999),
        })
        census["straddle"] += 1

        straddle.append(tid)

    for _ in range(8):
        tid += 1
        g.emit({"op": "begin", "txn": tid})

        for _ in range(r.randint(1, 2)):
            k = g.key()
            g.emit({
                "op": "set",
                "txn": tid,
                "key": k,
                "value": r.randint(1, 99),
            })

    delete_existing_keys = {
        g.key(): r.randint(10, 100)
        for _ in range(6)
    }
    delete_snapshot = {
        k: [value, 0]
        for k, value in delete_existing_keys.items()
    }

    delete_snapshot.update(straddle_snapshot)
    g.checkpoint(extra_state=delete_snapshot)

    for stid in straddle:
        g.commit(stid)

    for k in delete_existing_keys:
        tid += 1
        g.emit({"op": "begin", "txn": tid})
        g.emit({"op": "del", "txn": tid, "key": k})
        g.commit(tid)
        census["delete_existing"] += 1

    for _ in range(6):
        tid += 1
        k = g.key()

        g.emit({"op": "begin", "txn": tid})
        g.emit({
            "op": "add",
            "txn": tid,
            "key": k,
            "delta": r.randint(5, 60),
        })
        g.commit(tid)
        census["addmiss"] += 1

    for _ in range(6):
        tid += 1
        k = g.key()

        g.emit({"op": "begin", "txn": tid})
        g.emit({
            "op": "set",
            "txn": tid,
            "key": k,
            "value": r.randint(10, 100),
        })
        g.emit({"op": "del", "txn": tid, "key": k})
        g.commit(tid)

        census["delete"] += 1

    for _ in range(6):
        tid += 1
        k = g.key()

        g.emit({"op": "begin", "txn": tid})
        g.emit({
            "op": "set",
            "txn": tid,
            "key": k,
            "value": r.randint(10, 100),
        })
        g.emit({"op": "del", "txn": tid, "key": k})
        census["delete_uncommitted"] += 1

    for _ in range(60):
        tid += 1
        g.emit({"op": "begin", "txn": tid})

        for _ in range(r.randint(1, 3)):
            k = g.key()
            g.emit({
                "op": "set",
                "txn": tid,
                "key": k,
                "value": r.randint(-99, 99),
            })

            if r.random() < 0.3:
                g.emit({
                    "op": "add",
                    "txn": tid,
                    "key": k,
                    "delta": r.randint(1, 15),
                })

        if r.random() < 0.15:
            g.abort(tid)
        else:
            g.commit(tid)

    tid += 1
    xid = tid

    g.emit({"op": "begin", "txn": xid})

    for _ in range(3):
        k = g.key()
        g.emit({
            "op": "set",
            "txn": xid,
            "key": k,
            "value": r.randint(100, 200),
        })
        census["x_loser"] += 1

    lines = g.lines()

    ckey = g.key()
    lines.append(corrupt_line({
        "op": "set",
        "txn": xid,
        "key": ckey,
        "value": 777,
        "lsn": g.lsn + 1,
    }))

    lines.append(encode_record({
        "op": "commit",
        "txn": xid,
        "lsn": g.lsn + 2,
    }))

    yid = xid + 1
    r1 = g.key()

    lines.append(encode_record({
        "op": "begin",
        "txn": yid,
        "lsn": g.lsn + 3,
    }))

    lines.append(encode_record({
        "op": "set",
        "txn": yid,
        "key": r1,
        "value": 999,
        "lsn": g.lsn + 4,
    }))

    lines.append(encode_record({
        "op": "commit",
        "txn": yid,
        "lsn": g.lsn + 5,
    }))

    lines.append(_torn_tail())

    return lines, census


# ---- sample / live windows: no edge ---------------------------------------
def build_sample(seed, variant):
    g = Gen(seed)
    r = g.rng
    tid = 2000

    if variant == 2:
        pre = {}
        for _ in range(6):
            pre[g.key()] = [r.randint(-100, 100), 0]
        g.checkpoint_explicit(pre)

    for _ in range(16):
        tid += 1
        g.emit({"op": "begin", "txn": tid})

        for _ in range(r.randint(1, 3)):
            k = g.key()
            g.emit({
                "op": "set",
                "txn": tid,
                "key": k,
                "value": r.randint(-50, 50),
            })

            if variant == 3 and r.random() < 0.5:
                g.emit({
                    "op": "add",
                    "txn": tid,
                    "key": k,
                    "delta": r.randint(1, 20),
                })

            if variant == 3 and r.random() < 0.25:
                g.emit({"op": "del", "txn": tid, "key": k})

        roll = r.random()
        if roll < 0.12:
            g.abort(tid)
        elif roll < 0.20:
            pass
        else:
            g.commit(tid)

    return g.lines()


def build_live(seed):
    return build_sample(seed, 3)


# ---- CLI ------------------------------------------------------------------
def write_window(output_dir, seed, mode):
    if mode == "graded":
        lines = build_graded(seed)[0]
    elif mode == "live":
        lines = build_live(seed)
    elif mode.startswith("sample"):
        lines = build_sample(seed, int(mode[-1]))
    else:
        raise SystemExit("unknown mode %r" % mode)

    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "journal.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv):
    if len(argv) < 3:
        raise SystemExit("usage: generate_data.py <output_dir> <seed> [mode]")

    output_dir = argv[1]
    seed = int(argv[2])      # fixing the seed for making the randomized generation deterministic.
    mode = argv[3] if len(argv) > 3 else "graded"
    write_window(output_dir, seed, mode)


if __name__ == "__main__":
    main(sys.argv)
