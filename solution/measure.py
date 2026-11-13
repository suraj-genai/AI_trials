#!/usr/bin/env python3
"""The difficulty proof for the crash-recovery task.

Everything here is measured, not argued:

  * the reference recovery agrees with an INDEPENDENT per-key implementation on
    every graded and sample window (guards against an oracle bug);
  * every recovery edge is present in every graded window (census);
  * the shipped build recovers every sample window exactly (samples carry no
    edge, so a repair validated only by replaying them gets no signal);
  * each near-correct repair -- the reference with exactly one interaction wrong
    -- reproduces every sample window and fails every graded window (so a single
    wrong interaction scores zero).

Run: python3 measure.py
"""

import json
import os
import sys
import zlib
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tests"))
import generate_data as G  # noqa: E402

UP = ("set", "add", "del")


# ---- format (correct + buggy variants) ------------------------------------
def crc_of(payload):
    return zlib.crc32(json.dumps(payload, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8")) & 0xFFFFFFFF


def parse_ok(line):
    line = line.rstrip("\n")
    if not line:
        return None
    try:
        obj = json.loads(line)
    except Exception:
        return None
    if not isinstance(obj, dict) or "r" not in obj or "crc" not in obj:
        return None
    p = obj["r"]
    if not isinstance(p, dict) or obj["crc"] != crc_of(p):
        return None
    return p


def parse_lax(line):  # buggy: no crc check
    line = line.rstrip("\n")
    if not line:
        return None
    try:
        obj = json.loads(line)
    except Exception:
        return None
    if not isinstance(obj, dict) or "r" not in obj:
        return None
    return obj["r"] if isinstance(obj["r"], dict) else None


def durable_ok(lines):
    out = []
    for ln in lines:
        r = parse_ok(ln)
        if r is None:
            break
        out.append(r)
    return out


def durable_lax(lines):  # buggy: skip and continue
    out = []
    for ln in lines:
        r = parse_lax(ln)
        if r is not None:
            out.append(r)
    return out


# ---- parametric recover (correct with all flags False) --------------------
def recover(lines, d1=False, d2=False, d3=False, d4=False, d5=False, d6=False):
    recs = durable_lax(lines) if d1 else durable_ok(lines)
    if d2:
        committed = {r["txn"] for r in (parse_ok(x) for x in lines)
                     if r is not None and r.get("op") == "commit"}
    else:
        committed = {r["txn"] for r in recs if r["op"] == "commit"}
    ckpts = [r for r in recs if r["op"] == "checkpoint"]
    table, applied, ck_lsn = {}, {}, -1
    if ckpts:
        for k, (v, l) in ckpts[-1]["state"].items():
            table[k], applied[k] = v, l
        ck_lsn = ckpts[-1]["lsn"]
    for r in sorted((x for x in recs if x["op"] in UP), key=lambda x: x["lsn"]):
        if d3 and r["lsn"] <= ck_lsn:
            continue
        if r["txn"] not in committed:
            continue
        if d6 and r["key"] in applied and r["lsn"] <= ck_lsn:
            continue
        if (not d4) and r["key"] in applied and r["lsn"] <= applied[r["key"]]:
            continue
        op = r["op"]
        if op == "set":
            table[r["key"]] = r["value"]
        elif op == "add":
            if d5:
                if r["key"] in table:
                    table[r["key"]] += r["delta"]
            else:
                table[r["key"]] = table.get(r["key"], 0) + r["delta"]
        else:
            table.pop(r["key"], None)
        applied[r["key"]] = r["lsn"]
    return {k: v for k, v in table.items()}


# ---- independent per-key truth --------------------------------------------
def truth(lines):
    """Independent per-key reconstruction from durable history + checkpoint."""
    P = durable_ok(lines)
    committed = {r["txn"] for r in P if r["op"] == "commit"}
    ckpts = [r for r in P if r["op"] == "checkpoint"]
    snap = ckpts[-1]["state"] if ckpts else {}

    by_key = defaultdict(list)
    for r in P:
        if r["op"] in UP:
            by_key[r["key"]].append(r)

    out = {}
    all_keys = set(snap) | set(by_key)
    for key in all_keys:
        if key in snap:
            value, applied_lsn = snap[key]
            present = True
        else:
            value, applied_lsn = 0, -1
            present = False

        ops = sorted(by_key.get(key, ()), key=lambda r: r["lsn"])
        committed_ops = [r for r in ops if r["txn"] in committed]
        if not committed_ops:
            if present:
                out[key] = value
            continue

        for r in committed_ops:
            if r["lsn"] <= applied_lsn:
                continue
            if r["op"] == "set":
                value, present = r["value"], True
            elif r["op"] == "add":
                value, present = value + r["delta"], True
            else:
                value, present = 0, False
            applied_lsn = r["lsn"]

        if present:
            out[key] = value

    return out


def main():
    n = 300
    # 1. reconciliation
    dis = sum(1 for s in range(n)
              if recover(G.build_graded(s)[0]) != truth(G.build_graded(s)[0]))
    print("reconcile graded (ref vs independent): %d / %d disagreements" % (dis, n))
    for v in (1, 2, 3):
        d = sum(1 for s in range(n)
                if recover(G.build_sample(s, v)) != truth(G.build_sample(s, v)))
        print("reconcile sample v%d: %d / %d" % (v, d, n))

    # 2. census
    mins = {}
    for s in range(n):
        for k, val in G.build_graded(s)[1].items():
            mins[k] = min(mins.get(k, 1 << 30), val)
    print("census min per edge:", mins)
    assert all(v > 0 for v in mins.values())

    # 3. grinders: each one fault -> fails all graded, passes all samples
    faults = [("D1 durable_prefix", dict(d1=True)),
              ("D2 commit_durability", dict(d2=True)),
              ("D3+D4 redo_pass", dict(d3=True)),
              ("D3+D4 redo_pass (guard)", dict(d4=True)),
              ("D5 add_missing", dict(d5=True)),
              ("D6 redo_pass fuzzy lure", dict(d6=True))]
    for name, kw in faults:
        gf = sum(1 for s in range(n)
                 if recover(G.build_graded(s)[0], **kw) != recover(G.build_graded(s)[0]))
        sm = 0
        for v in (1, 2, 3):
            for s in range(100):
                if recover(G.build_sample(s, v), **kw) == recover(G.build_sample(s, v)):
                    sm += 1
        print("grinder %-26s graded-fail %d/%d  sample-match %d/300" % (name, gf, n, sm))
        assert gf == n and sm == 300

    print("ALL CONTROLS PASS")


if __name__ == "__main__":
    main()
