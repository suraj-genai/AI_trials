#!/bin/bash
# Runs inside the SHARED environment image (environment/Dockerfile). pytest and
# its CTRF plugin are baked in, so nothing is installed or downloaded here.
#
# The grade is NOT pytest's exit status. pytest writes a structured report into
# a private directory; /tests/arbiter.py then decides the run independently,
# after checking that the grading files are the ones this task shipped. The
# pytest status is passed to the arbiter as a condition on that verdict.
{
set +e

# The grade this run will carry unless the arbiter says otherwise, written
# before any of the work: a run that is killed, truncated or short-circuited
# part way leaves a 0 behind rather than whatever was there before. The whole
# script is one brace group so bash reads it in full before running any of it.
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

# Every external command below -- the interpreter included -- is resolved
# through PATH, and the two directories PATH searches first (/usr/local/sbin,
# /usr/local/bin) are writable by the root agent phase that precedes grading. A
# stand-in `python3`, `find` or `chmod` left there would otherwise decide the
# run. PATH is pinned to the system directories, the interpreter is named by
# absolute path, and the run fails closed (leaving the 0 already on disk) if the
# interpreter is not where it is expected.
export PATH=/usr/bin:/bin
PYBIN=/usr/bin/python3
if [ ! -x "$PYBIN" ]; then
  exit 0
fi

# The reference build, the generator and the grading suite belong to root and
# to nobody else. Every run of the repaired build is started unprivileged, so
# from here on a repair cannot open the reference it is measured against; the
# suite, the generator and the arbiter still read them as root. The agent's own
# tree is left traversable so that a repair with an unusual umask still runs.
chown -R root:root /tests
find /tests -type d -exec chmod 700 {} +
find /tests -type f -exec chmod 600 {} +
chmod -R a+rX /app/store /app/data 2>/dev/null
find /app -xdev \( -perm -4000 -o -perm -2000 \) -exec chmod a-s {} + 2>/dev/null

REPORT_DIR="$(mktemp -d)"
chmod 700 "$REPORT_DIR"
REPORT="${REPORT_DIR}/ctrf.json"

cd /
# -S is not implied by -I. -I gives -E -P -s, and the lowercase -s only skips
# the *user* site directory; -S is what suppresses the `site` module itself,
# and with it both sitecustomize/usercustomize and any .pth file left on a site
# directory -- measured on this image, a sitecustomize.py planted by the agent
# phase forged a passing report and scored 1 without -S. Suppressing `site`
# also drops the dist-packages directories it would have added, so the two the
# image installs pytest into are put back explicitly and by path: they are read
# as ordinary import roots, with none of site's startup execution.
PYTHONSAFEPATH=1 \
PYTHONNOUSERSITE=1 \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
"$PYBIN" -I -S -P -B -c '
import sys
sys.path[:0] = ["/usr/local/lib/python3.%d/dist-packages" % sys.version_info[1],
                "/usr/lib/python3/dist-packages"]
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
' \
    -p ctrf.main \
    -c /tests/pytest.ini \
    --rootdir=/tests \
    --confcutdir=/tests \
    --noconftest \
    -p no:cacheprovider \
    --ctrf "$REPORT" \
    /tests/test_outputs.py -rA
PYTEST_RC=$?

cp "$REPORT" /logs/verifier/ctrf.json 2>/dev/null
if [ ! -s /logs/verifier/ctrf.json ]; then
  cat > /logs/verifier/ctrf.json <<JSON
{"results":{"summary":{"tests":0,"passed":0,"failed":1,"skipped":0},"tests":[{"name":"pytest startup","status":"failed","message":"pytest did not produce a CTRF report"}]}}
JSON
fi

"$PYBIN" -I -S -B /tests/arbiter.py "$REPORT" "$PYTEST_RC"
ARBITER_RC=$?

rm -rf "$REPORT_DIR"

if [ $ARBITER_RC -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi

exit 0
}
