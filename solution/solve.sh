#!/bin/bash
# Reference solution (oracle). Genuinely perform the task — run the real
# build/command/pipeline that produces the required end-state. It must reach the
# end-state the tests check and score 1.0 under `rv oracle`. Do not hand-write
# the values the hidden tests check.

set -euo pipefail

python3 /solution/solve.py
