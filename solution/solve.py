#!/usr/bin/env python3
"""Reference repair: install the corrected store modules over /app/store and
run one recovery end to end.

The corrected sources live beside this script under ``store/``, one file per
module, keeping the names and signatures the shipped build had. What changes is
what they compute: the durable log ends at the first torn or corrupt record and
the residue behind it is dropped; a commit is honoured only inside that durable
log; recovery repeats history from the start against the last checkpoint's
snapshot, skipping updates already reflected in it; and an ``add`` to a key with
no value yet treats the missing value as zero. ``findings.json`` names the four
rules the shipped build broke.
"""

import os
import shutil
import subprocess
import sys

SOURCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store")
STORE_DIR = "/app/store"


def main():
    for name in sorted(os.listdir(SOURCE_DIR)):
        if name.endswith(".py"):
            shutil.copyfile(os.path.join(SOURCE_DIR, name),
                            os.path.join(STORE_DIR, name))
    cache = os.path.join(STORE_DIR, "__pycache__")
    if os.path.isdir(cache):
        shutil.rmtree(cache)
    subprocess.run([sys.executable, os.path.join(STORE_DIR, "main.py")], check=True)


if __name__ == "__main__":
    main()
