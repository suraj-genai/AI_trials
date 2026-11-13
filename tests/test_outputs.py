"""Grades the repaired crash-recovery build.

Draws fresh held-out journals, recovers each with the agent's build and with the
plant's own build in /tests/oracle over the identical bytes, and compares the
recovered tables. The reference build is root-only and the agent never sees it;
every run of the agent's build is started stripped of privilege.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

sys.path.insert(0, "/tests")
import generate_data as gen  # trusted, root-only, manifest-pinned

AGENT_STORE = "/app/store"
ORACLE_STORE = "/tests/oracle"
DATA_GENERATOR = "/tests/generate_data.py"

UNPRIVILEGED_UID = 65534
UNPRIVILEGED_GID = 65534

TIME_LIMIT_SEC = 10
RUN_CEILING_SEC = 30

GRADED_SEED_1 = 104729
GRADED_SEED_2 = 104759

EXPECTED_RULES = {"add_missing", "commit_durability", "durable_prefix", "redo_pass"}
VOCABULARY = {
    "durable_prefix",
    "commit_durability",
    "redo_pass",
    "add_missing",
}

ENTRY_POINTS = {
    "wal": {"parse_line": ["line"], "durable_prefix": ["lines"]},
    "recovery": {"recover": ["lines"]},
    "main": {"main": ["data_dir", "output_dir"]},
}


def _spawn(argv, unprivileged, **kwargs):
    if unprivileged:
        kwargs.update(user=UNPRIVILEGED_UID, group=UNPRIVILEGED_GID, extra_groups=[])
    return subprocess.run(argv, **kwargs)


def _purge_bytecode(directory):
    cache = os.path.join(directory, "__pycache__")
    if os.path.isdir(cache):
        shutil.rmtree(cache, ignore_errors=True)


def _scratch(path, unprivileged):
    os.makedirs(path, exist_ok=True)
    if unprivileged:
        os.chmod(path, 0o777)
    return path


def _write_journal(data_dir, lines):
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "journal.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _gen_graded(data_dir, seed):
    subprocess.run(
        [sys.executable, DATA_GENERATOR, data_dir, str(seed), "graded"],
        check=True,
        timeout=60,
    )
    return seed


_RUNNER = '''
import os
import sys
STORE = {store!r}
sys.path.insert(0, STORE)
import main as store_main
actual = os.path.realpath(store_main.__file__)
expected = os.path.realpath(os.path.join(STORE, "main.py"))
if actual != expected:
    raise SystemExit("main resolved to %s, expected %s" % (actual, expected))
store_main.main(data_dir={data_dir!r}, output_dir={output_dir!r})
'''


def _run_store(store_dir, data_dir, out_dir, unprivileged=True,
               timeout=RUN_CEILING_SEC):
    _scratch(out_dir, unprivileged)
    _purge_bytecode(store_dir)
    runner = os.path.join(out_dir, "_runner.py")
    with open(runner, "w") as fh:
        fh.write(_RUNNER.format(store=store_dir, data_dir=data_dir, output_dir=out_dir))
    os.chmod(runner, 0o644)
    try:
        result = _spawn([sys.executable, "-I", "-B", runner], unprivileged,
                        capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AssertionError("recovery did not finish within %ds" % timeout)
    assert result.returncode == 0, "recovery failed:\n%s" % result.stderr
    with open(os.path.join(out_dir, "state.json")) as fh:
        state = json.load(fh)
    findings = None
    fpath = os.path.join(out_dir, "findings.json")
    if os.path.exists(fpath):
        with open(fpath) as fh:
            findings = json.load(fh)
    return state, findings


def _recover_both(lines):
    with tempfile.TemporaryDirectory() as ref, tempfile.TemporaryDirectory() as ag:
        os.chmod(ag, 0o755)
        adata, aout = os.path.join(ag, "d"), os.path.join(ag, "o")
        odata, oout = os.path.join(ref, "d"), os.path.join(ref, "o")
        _write_journal(adata, lines)
        _write_journal(odata, lines)
        astate, afind = _run_store(AGENT_STORE, adata, aout, unprivileged=True)
        ostate, ofind = _run_store(ORACLE_STORE, odata, oout, unprivileged=False)
        return astate, afind, ostate, ofind


@pytest.fixture(scope="module")
def graded():
    with tempfile.TemporaryDirectory() as ref, tempfile.TemporaryDirectory() as ag:
        os.chmod(ag, 0o755)
        src = os.path.join(ref, "src")
        _gen_graded(src, GRADED_SEED_1)
        with open(os.path.join(src, "journal.log")) as fh:
            lines = fh.read().splitlines()
        adata, aout = os.path.join(ag, "d"), os.path.join(ag, "o")
        odata, oout = os.path.join(ref, "d"), os.path.join(ref, "o")
        _write_journal(adata, lines)
        _write_journal(odata, lines)
        astate, afind = _run_store(AGENT_STORE, adata, aout, unprivileged=True)
        ostate, ofind = _run_store(ORACLE_STORE, odata, oout, unprivileged=False)
        yield astate, afind, ostate, ofind


def _assert_entry_points(store_dir):
    script = '''
import inspect, os, sys
root = {store!r}
sys.path.insert(0, root)
import wal, recovery, main
mods = {{"wal": wal, "recovery": recovery, "main": main}}
eps = {eps!r}
for name, mod in mods.items():
    actual = os.path.realpath(mod.__file__)
    expected = os.path.realpath(os.path.join(root, name + ".py"))
    if actual != expected:
        raise SystemExit("%s resolved to %s, expected %s" % (name, actual, expected))
    for fn, want in eps[name].items():
        f = getattr(mod, fn, None)
        if not callable(f):
            raise SystemExit("%s.%s missing or not callable" % (name, fn))
        got = list(inspect.signature(f).parameters)
        if got != want:
            raise SystemExit("%s.%s has params %r, expected %r" % (name, fn, got, want))
'''
    result = _spawn([sys.executable, "-I", "-B", "-c",
                     script.format(store=store_dir, eps=ENTRY_POINTS)],
                    True, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def _agent_wal(func, arg):
    script = '''
import json, sys
sys.path.insert(0, {store!r})
import wal
arg = json.load(sys.stdin)
out = getattr(wal, {func!r})(arg)
if {func!r} == "durable_prefix":
    print(json.dumps(len(out)))
else:
    print(json.dumps(out))
'''
    result = _spawn([sys.executable, "-I", "-B", "-c",
                     script.format(store=AGENT_STORE, func=func)],
                    True, input=json.dumps(arg), capture_output=True,
                    text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# ---- micro journals (hand-built, one edge each) ---------------------------
def _micro_truncation():
    g = gen.Gen(1)
    g.emit({"op": "begin", "txn": 1})
    g.emit({"op": "set", "txn": 1, "key": "A", "value": 10})
    g.commit(1)
    g.emit({"op": "begin", "txn": 2})
    g.emit({"op": "set", "txn": 2, "key": "B", "value": 20})
    lines = g.lines()
    lines.append(gen.corrupt_line({"op": "set", "txn": 2, "key": "C",
                                   "value": 99, "lsn": g.lsn + 1}))
    lines.append(gen.encode_record({"op": "commit", "txn": 2, "lsn": g.lsn + 2}))
    lines.append(gen.encode_record({"op": "begin", "txn": 3, "lsn": g.lsn + 3}))
    lines.append(gen.encode_record({"op": "set", "txn": 3, "key": "D",
                                    "value": 77, "lsn": g.lsn + 4}))
    lines.append(gen.encode_record({"op": "commit", "txn": 3, "lsn": g.lsn + 5}))
    return lines


def _micro_fuzzy_checkpoint():
    g = gen.Gen(2)
    g.emit({"op": "begin", "txn": 1})
    g.emit({"op": "add", "txn": 1, "key": "K1", "delta": 5})
    g.commit(1)
    g.emit({"op": "begin", "txn": 2})
    g.emit({"op": "add", "txn": 2, "key": "K1", "delta": 7})
    g.emit({"op": "set", "txn": 2, "key": "K2", "value": 100})
    g.checkpoint()
    g.commit(2)
    return g.lines()


def _micro_add_missing_and_deletes():
    g = gen.Gen(3)

    g.emit({"op": "begin", "txn": 1})
    g.emit({"op": "add", "txn": 1, "key": "M", "delta": 7})
    g.commit(1)

    g.checkpoint_explicit({"EXIST": [42, 0]})
    g.emit({"op": "begin", "txn": 2})
    g.emit({"op": "del", "txn": 2, "key": "EXIST"})
    g.commit(2)

    g.emit({"op": "begin", "txn": 3})
    g.emit({"op": "set", "txn": 3, "key": "TEMP", "value": 99})
    g.emit({"op": "del", "txn": 3, "key": "TEMP"})
    g.commit(3)

    g.emit({"op": "begin", "txn": 4})
    g.emit({"op": "set", "txn": 4, "key": "LOSER", "value": 77})
    g.emit({"op": "del", "txn": 4, "key": "LOSER"})

    g.emit({"op": "begin", "txn": 5})
    g.emit({"op": "set", "txn": 5, "key": "N", "value": 3})
    g.emit({"op": "begin", "txn": 6})
    g.emit({"op": "set", "txn": 6, "key": "P", "value": 9})
    g.abort(6)
    return g.lines()


# ===========================================================================
def test_entry_points_keep_documented_signatures():
    """Verify the documented entry points remain accessible."""
    _assert_entry_points(AGENT_STORE)


def test_recovered_state_exact_match(graded):
    """Verify state recovery against the reference."""
    astate, _afind, ostate, _ofind = graded
    missing = {k: ostate[k] for k in list(ostate) if k not in astate}
    extra = {k: astate[k] for k in list(astate) if k not in ostate}
    wrong = {k: (astate[k], ostate[k]) for k in ostate
             if k in astate and astate[k] != ostate[k]}
    assert astate == ostate, (
        "recovered table mismatch: %d missing (e.g. %s), %d extra (e.g. %s), "
        "%d wrong-value (e.g. %s)" % (
            len(missing), dict(list(missing.items())[:5]),
            len(extra), dict(list(extra.items())[:5]),
            len(wrong), dict(list(wrong.items())[:5])))


def test_findings_report_names_repaired_rules(graded):
    """Verify the findings report structure and vocabulary."""
    _astate, afind, _ostate, ofind = graded
    assert afind is not None, "no findings.json was written"
    assert isinstance(afind, dict) and isinstance(afind.get("rules"), list), \
        "findings.json must be an object with a 'rules' list"
    reported = set(afind["rules"])
    assert reported <= VOCABULARY, (
        "findings names rules outside the vocabulary: %s" % sorted(reported - VOCABULARY))
    assert reported == EXPECTED_RULES, (
        "findings rules %s; expected %s" % (sorted(reported), sorted(EXPECTED_RULES)))
    assert set(ofind["rules"]) == EXPECTED_RULES


def test_second_independent_window():
    """Verify recovery consistency across independent test windows."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src")
        _gen_graded(src, GRADED_SEED_2)
        with open(os.path.join(src, "journal.log")) as fh:
            lines = fh.read().splitlines()
    astate, _af, ostate, _of = _recover_both(lines)
    assert astate == ostate, "second window: recovered table does not match reference"


def test_micro_truncation_and_residue():
    """Verify recovery from truncated log entries."""
    astate, _af, ostate, _of = _recover_both(_micro_truncation())
    assert astate == ostate == {"A": 10}, (
        "expected {'A': 10}; agent=%s reference=%s" % (astate, ostate))


def test_micro_fuzzy_checkpoint_straddle():
    """Verify recovery behavior with concurrent checkpoint operations."""
    astate, _af, ostate, _of = _recover_both(_micro_fuzzy_checkpoint())
    assert astate == ostate == {"K1": 5, "K2": 100}, (
        "expected {'K1': 5, 'K2': 100}; agent=%s reference=%s" % (astate, ostate))


def test_micro_add_missing_and_losers():
    """Verify recovery of add operations and dropped transactions."""
    astate, _af, ostate, _of = _recover_both(_micro_add_missing())
    assert astate == ostate == {"M": 7}, (
        "expected {'M': 7}; agent=%s reference=%s" % (astate, ostate))


def test_durable_prefix_stops_at_corruption():
    """Verify log parsing stops at the first corrupt record."""
    g = gen.Gen(5)
    for i in range(6):
        g.emit({"op": "begin", "txn": 500 + i})
        g.emit({"op": "set", "txn": 500 + i, "key": "k%d" % i, "value": i})
        g.commit(500 + i)
    good = len(g.recs)
    lines = g.lines()
    lines.append(gen.corrupt_line({"op": "set", "txn": 999, "key": "z",
                                   "value": 1, "lsn": g.lsn + 1}))
    lines.append(gen.encode_record({"op": "set", "txn": 999, "key": "y",
                                    "value": 2, "lsn": g.lsn + 2}))
    got = _agent_wal("durable_prefix", lines)
    assert got == good, "durable_prefix returned %d records, the durable log has %d" % (got, good)


def test_parse_line_validates_checksum():
    """Verify record parsing validates checksums."""
    payload = {"op": "commit", "txn": 7, "lsn": 3}
    assert _agent_wal("parse_line", gen.encode_record(payload)) == payload
    assert _agent_wal("parse_line", gen.corrupt_line(payload)) is None


def test_recovery_is_deterministic():
    """Verify recovery produces consistent results on fixed input."""
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src")
        _gen_graded(src, GRADED_SEED_1)
        with open(os.path.join(src, "journal.log")) as fh:
            lines = fh.read().splitlines()
    a1, _1, _o1, _2 = _recover_both(lines)
    a2, _3, _o2, _4 = _recover_both(lines)
    assert a1 == a2, "recovery is not deterministic on a fixed window"


def test_state_json_shape(graded):
    """Verify the output format of recovered state."""
    astate, _af, _os, _of = graded
    assert isinstance(astate, dict) and astate, "state.json is empty or not an object"
    assert all(isinstance(k, str) for k in astate), "state keys must be strings"
    assert all(isinstance(v, int) and not isinstance(v, bool)
               for v in astate.values()), "state values must be integers"


def test_recovery_within_time_limit():
    """Verify recovery completes within performance constraints."""
    with tempfile.TemporaryDirectory() as d:
        os.chmod(d, 0o755)
        src, out = os.path.join(d, "src"), os.path.join(d, "out")
        _gen_graded(src, GRADED_SEED_1)
        _purge_bytecode(AGENT_STORE)
        start = time.time()
        _run_store(AGENT_STORE, src, out, unprivileged=True, timeout=RUN_CEILING_SEC)
        elapsed = time.time() - start
        assert elapsed < TIME_LIMIT_SEC, "recovery took %.1fs (limit %ds)" % (elapsed, TIME_LIMIT_SEC)


def test_live_journal_selftest():
    """Verify the build produces both required outputs."""
    with tempfile.TemporaryDirectory() as d:
        os.chmod(d, 0o755)
        out = os.path.join(d, "out")
        state, findings = _run_store(AGENT_STORE, "/app/data", out, unprivileged=True)
        assert isinstance(state, dict), "state.json is not an object"
        assert findings is not None and isinstance(findings.get("rules"), list), \
            "findings.json missing or malformed"