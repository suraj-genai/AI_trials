#!/usr/bin/env python3
"""Independent arbiter for the crash-recovery verifier.

Decides the run's outcome from the structured pytest report rather than from
pytest's exit status, and refuses to decide at all unless the grading files are
the ones this task shipped. Run under ``python3 -I -S -B``.

    arbiter.py <ctrf_report> <pytest_rc>
    arbiter.py --write-manifest
"""

import hashlib
import json
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(TESTS_DIR, "manifest.sha256")
REWARD_PATH = os.path.join("/logs", "verifier", "reward.txt")

# Files whose contents decide the grade. Any edit to one of these invalidates
# the run unless the manifest is regenerated with it.
GRADING_FILES = (
    "arbiter.py",
    "generate_data.py",
    "test_outputs.py",
    os.path.join("oracle", "wal.py"),
    os.path.join("oracle", "recovery.py"),
    os.path.join("oracle", "main.py"),
)

# The suite grades this many checks. A run that reports a different number has
# had tests deselected, added or collected differently, and is not a verdict.
EXPECTED_TESTS = 13


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest():
    lines = []
    for name in GRADING_FILES:
        lines.append("%s  %s" % (digest(os.path.join(TESTS_DIR, name)), name))
    with open(MANIFEST, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    sys.stderr.write("wrote %s (%d files)\n" % (MANIFEST, len(lines)))


def refuse_symlinks(path):
    """No component of `path` may be a symlink, and neither may `path`."""
    if os.path.islink(path):
        raise SystemExit("arbiter: refusing symlink at %s" % path)
    parent = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.islink(parent):
            raise SystemExit("arbiter: refusing symlink at %s" % parent)
        nxt = os.path.dirname(parent)
        if nxt == parent:
            return
        parent = nxt


def check_manifest():
    if not os.path.isfile(MANIFEST):
        raise SystemExit("arbiter: no manifest")
    want = {}
    with open(MANIFEST) as fh:
        for line in fh:
            line = line.strip()
            if line:
                got, name = line.split("  ", 1)
                want[name] = got
    if set(want) != set(GRADING_FILES):
        raise SystemExit("arbiter: manifest does not cover the grading files")
    for name, expected in sorted(want.items()):
        path = os.path.join(TESTS_DIR, name)
        refuse_symlinks(path)
        if digest(path) != expected:
            raise SystemExit("arbiter: %s is not the file this task shipped" % name)


def read_outcome(report_path):
    refuse_symlinks(report_path)
    if not os.path.isfile(report_path):
        raise SystemExit("arbiter: pytest wrote no report")
    with open(report_path) as fh:
        report = json.load(fh)

    results = report.get("results", {})
    summary = results.get("summary", {})
    tests = results.get("tests", [])

    failed = int(summary.get("failed", 0))
    passed = int(summary.get("passed", 0))
    skipped = int(summary.get("skipped", 0))
    pending = int(summary.get("pending", 0))
    other = int(summary.get("other", 0))
    total = int(summary.get("tests", len(tests)))

    names = sorted(t.get("name", "") for t in tests)
    if len(set(names)) != len(names):
        raise SystemExit("arbiter: duplicate test names in the report")

    reasons = []
    if total != EXPECTED_TESTS:
        reasons.append("reported %d checks, expected %d" % (total, EXPECTED_TESTS))
    if passed != EXPECTED_TESTS:
        reasons.append("%d of %d checks passed" % (passed, EXPECTED_TESTS))
    if failed or skipped or pending or other:
        reasons.append("failed=%d skipped=%d pending=%d other=%d"
                       % (failed, skipped, pending, other))
    for test in tests:
        if test.get("status") != "passed":
            reasons.append("%s: %s" % (test.get("name"), test.get("status")))
    return reasons


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--write-manifest":
        write_manifest()
        return 0

    if len(sys.argv) != 3:
        sys.stderr.write(__doc__)
        return 2

    report_path, pytest_rc = sys.argv[1], sys.argv[2]
    check_manifest()
    reasons = read_outcome(report_path)

    # The pytest exit status is a condition on the verdict, never the verdict.
    if pytest_rc != "0":
        reasons.append("pytest exited %s" % pytest_rc)

    refuse_symlinks(REWARD_PATH)
    if reasons:
        for reason in reasons:
            sys.stderr.write("arbiter: %s\n" % reason)
        return 1
    sys.stderr.write("arbiter: all %d checks passed\n" % EXPECTED_TESTS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
