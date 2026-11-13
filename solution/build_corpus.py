#!/usr/bin/env python3
"""Regenerate the shipped corpus and assert its structural properties.

Writes the three sample windows (journal + expected recovered state) and the
image's live journal, then checks that no sample exercises a recovery edge (the
shipped build recovers every sample exactly), and that a freshly drawn graded
window carries all of them. Run from the task root or anywhere; paths are
resolved from this file.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(HERE)
TESTS = os.path.join(TASK, "tests")
ORACLE = os.path.join(TESTS, "oracle")
ENV_DATA = os.path.join(TASK, "environment", "data")

sys.path.insert(0, TESTS)
import generate_data as G  # noqa: E402

SAMPLES = [(1, 101), (2, 102), (3, 103)]
LIVE_SEED = 201


def _oracle_recover(lines):
    """Recover with the reference store, isolated from any other `wal` module."""
    saved = dict(sys.modules)
    sys.path.insert(0, ORACLE)
    try:
        for name in ("wal", "recovery"):
            sys.modules.pop(name, None)
        import recovery
        return recovery.recover(lines)
    finally:
        sys.path.remove(ORACLE)
        for name in ("wal", "recovery"):
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                sys.modules.pop(name, None)


def _buggy_recover(lines):
    saved = dict(sys.modules)
    store = os.path.join(TASK, "environment", "store")
    sys.path.insert(0, store)
    try:
        for name in ("wal", "recovery"):
            sys.modules.pop(name, None)
        import recovery
        return recovery.recover(lines)
    finally:
        sys.path.remove(store)
        for name in ("wal", "recovery"):
            if name in saved:
                sys.modules[name] = saved[name]
            else:
                sys.modules.pop(name, None)


def write_samples():
    for variant, seed in SAMPLES:
        lines = G.build_sample(seed, variant)
        state = _oracle_recover(lines)
        d = os.path.join(ENV_DATA, "samples", "case_%02d" % variant)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "journal.log"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True, indent=2)
    lines = G.build_live(LIVE_SEED)
    with open(os.path.join(ENV_DATA, "journal.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def assert_properties():
    # samples carry no edge: the shipped build recovers every one exactly
    bad = 0
    for variant, seed in SAMPLES:
        lines = G.build_sample(seed, variant)
        if _buggy_recover(lines) != _oracle_recover(lines):
            bad += 1
    live = G.build_live(LIVE_SEED)
    if _buggy_recover(live) != _oracle_recover(live):
        bad += 1
    assert bad == 0, "a shipped window exercises a recovery edge (%d)" % bad

    # a freshly drawn graded window carries every edge, and the shipped build
    # fails it
    for seed in range(50):
        _lines, census = G.build_graded(seed)
        assert all(v > 0 for v in census.values()), \
            "graded seed %d misses an edge: %s" % (seed, census)
        if _buggy_recover(_lines) == _oracle_recover(_lines):
            raise AssertionError("shipped build passes graded seed %d" % seed)
    print("build_corpus: samples edge-free, graded windows carry all edges. OK")


if __name__ == "__main__":
    write_samples()
    assert_properties()
