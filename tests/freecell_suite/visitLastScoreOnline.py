#!/usr/bin/env python3
"""visitLastScoreOnline: same cases as visitLastScore.

Naming this module (or running it alone) runs that same flow.

Run:  ./.venv/bin/python -u tests/freecell_suite/visitLastScoreOnline.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]

import fc  # noqa: E402
import visitLastScore  # noqa: E402


def run() -> None:
    visitLastScore.run()


if __name__ == "__main__":
    fc.main(run)
