#!/usr/bin/env python3
"""Verify the committed public test data, and fetch the parts kept out of git.

Every file under tests/public/ is listed in PROVENANCE.json with its source URL
and sha256. Two kinds are not committed:

  - the two large ReconRiver packs (month-end-close, failure-recovery, ~10 MB),
    to keep the repository small;
  - the cuadrador bank-vs-books set, whose source repository states no
    license, so it is fetched on demand and never redistributed from here.

    python tests/public/fetch_public.py --verify   # check what is on disk
    python tests/public/fetch_public.py            # fetch missing files, then verify

A file whose bytes differ from the manifest is reported and, when fetched,
discarded: a test case that silently changed no longer matches its answer key.
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MANIFEST = os.path.join(HERE, "PROVENANCE.json")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true",
                    help="only check files already on disk; download nothing")
    a = ap.parse_args()

    files = json.load(open(MANIFEST, encoding="utf-8"))["files"]
    bad, missing, fetched = [], [], 0
    for e in files:
        path = os.path.join(ROOT, e["path"])
        if not os.path.exists(path):
            if e["committed"]:
                missing.append(e["path"])
                continue
            if a.verify:
                continue
            with urllib.request.urlopen(e["source"], timeout=60) as r:
                data = r.read()
            if sha256(data) != e["sha256"]:
                bad.append(f"{e['path']} (download differs from manifest, discarded)")
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
            fetched += 1
            continue
        with open(path, "rb") as fh:
            if sha256(fh.read()) != e["sha256"]:
                bad.append(e["path"])

    present = sum(os.path.exists(os.path.join(ROOT, e["path"])) for e in files)
    print(f"{present}/{len(files)} files present, {fetched} fetched")
    for p in missing:
        print(f"  MISSING (should be committed): {p}")
    for p in bad:
        print(f"  CHANGED: {p}")
    sys.exit(1 if bad or missing else 0)


if __name__ == "__main__":
    main()
