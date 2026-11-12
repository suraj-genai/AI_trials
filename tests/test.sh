#!/bin/bash
#
# Standard TerminalCraft verifier. The only task specific file is
# tests/test_outputs.py, which this runs. Keep the reward tail below byte
# identical across every task: pytest exits 0 -> reward 1, otherwise reward 0.
#
# -I is load-bearing, not style. `-m` puts the cwd on sys.path[0] and python
# honours PYTHON* env vars. The verifier shares a container with the agent, so
# without -I the agent can shadow a module the suite imports, or point
# PYTHONPATH at its own code, and grade itself.

mkdir -p /logs/verifier
python3 -I -m pytest /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
  echo '{"reward": 1.0, "resolved": 1}' > /logs/verifier/reward.json
else
  echo 0 > /logs/verifier/reward.txt
  echo '{"reward": 0.0, "resolved": 0}' > /logs/verifier/reward.json
fi
